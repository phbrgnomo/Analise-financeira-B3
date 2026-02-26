#!/usr/bin/env python3
"""Gerar e validar checksums de snapshots.

Usage:
    python scripts/validate_snapshots.py --dir snapshots \
        --manifest snapshots/checksums.json
    python scripts/validate_snapshots.py --dir snapshots \
        --manifest snapshots/checksums.json --update
"""


from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, NoReturn, Tuple

logger = logging.getLogger(__name__)

# Ensure repo root is on sys.path so `from src...` imports work when the
# script is executed directly (e.g. `python scripts/validate_snapshots.py`).
# scripts/ is at repo_root/scripts, so repo_root is two parents up from here.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Note: avoid importing from `src` at module import time because some CI
# linting hooks require imports to be at the top of the file. We import
# `SNAPSHOTS_DIR` dynamically inside `main()` after ensuring the repo root
# is on `sys.path`.


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(directory: Path, pattern: str = "*") -> Dict[str, Dict[str, str]]:
    """Generate a manifest of files under `directory` matching `pattern`.

    Default behavior (pattern="*") preserves legacy behavior used by tests
    (includes all files). When validating snapshots we pass `pattern="*.csv"`
    to include only CSV snapshot files and ignore auxiliary files like
    `.checksum` and the manifest itself.
    """
    out: Dict[str, Dict[str, str]] = {}
    for p in sorted(directory.rglob(pattern)):
        if p.is_file():
            rel = str(p.as_posix())
            out[rel] = {"sha256": sha256_of_file(p)}
    return out


def load_manifest(path: Path) -> Dict[str, Dict[str, str]]:
    """Load and normalize a manifest file to a mapping of file -> metadata.

    The manifest file may be either the raw files mapping (legacy) or a
    payload containing a top-level `files` key (current format). This
    function validates the shape and returns a cleaned
    `Dict[str, Dict[str, str]]` mapping suitable for downstream callers.
    """
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid manifest format at {path}: expected JSON object")

    # Allow payload with `files` key or a direct files mapping
    if "files" in data and isinstance(data["files"], dict):
        raw = data["files"]
    else:
        raw = data

    manifest: Dict[str, Dict[str, str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ValueError(f"Invalid manifest key {key!r} at {path}: expected string")
        if not isinstance(value, dict):
            raise ValueError(
                f"Invalid manifest entry for {key!r} at {path}: expected object value"
            )
        normalized: Dict[str, str] = {}
        for sub_k, sub_v in value.items():
            if not isinstance(sub_k, str):
                raise ValueError(
                    f"Invalid manifest sub-key {sub_k!r} for {key!r} at {path}: "
                    "expected string keys"
                )
            if not isinstance(sub_v, str):
                raise ValueError(
                    f"Invalid manifest value for {key!r}.{sub_k!r} at {path}: "
                    "expected string value"
                )
            normalized[sub_k] = sub_v
        manifest[key] = normalized

    return manifest


def compare_manifests(
    expected: Dict[str, Dict[str, str]],
    current: Dict[str, Dict[str, str]],
) -> Tuple[bool, Dict[str, Tuple[str, str]]]:
    diffs = {}
    ok = True
    # Check for mismatches and missing files
    for path, meta in expected.items():
        exp = meta.get("sha256")
        cur = current.get(path, {}).get("sha256")
        if cur is None:
            diffs[path] = (exp, None)
            ok = False
        elif cur != exp:
            diffs[path] = (exp, cur)
            ok = False

    # Check for unexpected new files
    for path in current:
        if path not in expected:
            diffs[path] = (None, current[path].get("sha256"))
            ok = False

    return ok, diffs


def write_manifest(
    path: Path, manifest: Dict[str, Dict[str, str]], allow_external: bool = True
):
    # Delegate to helpers for clarity and to reduce cyclomatic complexity
    _validate_manifest_structure(manifest)
    target = _prepare_manifest_target(path, allow_external)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "files": manifest,
    }

    _atomic_write_json(target, payload)


def _validate_manifest_structure(manifest: object) -> None:
    """Validate that manifest is a mapping of str -> mapping of str->str."""
    if not isinstance(manifest, dict):
        raise TypeError("manifest must be a mapping of file -> metadata")
    for k, v in manifest.items():
        if not isinstance(k, str):
            raise ValueError("manifest keys must be strings")
        if not isinstance(v, dict):
            raise ValueError("manifest values must be mappings/dicts")
        for sub_k, sub_v in v.items():
            if not isinstance(sub_k, str) or not isinstance(sub_v, str):
                raise ValueError("manifest nested keys and values must be strings")


def _prepare_manifest_target(path: Path, allow_external: bool) -> Path:
    """Validate and prepare the target Path; return resolved Path.

    Ensures parent exists and is not a symlink. Performs CLI-only
    directory restriction when `allow_external` is False.
    """
    raw = str(path)
    if "\x00" in raw:
        raise ValueError("Invalid manifest path: contains null byte")

    if not allow_external:
        _validate_manifest_path(path)

    target = Path(path).resolve()
    parent = target.parent

    # Detect symlinks before creating directories to avoid creating
    # directories under a symlink target.
    if parent.exists() and parent.is_symlink():
        raise OSError("Refusing to write manifest into symlinked directory")

    parent.mkdir(parents=True, exist_ok=True)
    return target


def _atomic_write_json(target: Path, payload: object) -> None:
    """Atomically write JSON payload into `target` within its directory."""
    import tempfile

    parent = target.parent
    temp_name = None
    tf = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(parent),
        delete=False,
    )
    try:
        json.dump(payload, tf, indent=2, ensure_ascii=False)
        tf.flush()
        os.fsync(tf.fileno())
        temp_name = tf.name
        tf.close()
        os.replace(temp_name, str(target))
        temp_name = None
    finally:
        with contextlib.suppress(Exception):
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)


def _validate_manifest_path(path):
    raw = str(path)
    if "\x00" in raw:
        raise ValueError("Invalid manifest path: contains null byte")
    real = os.path.realpath(raw)
    allowed_dir = str((_REPO_ROOT / "snapshots").resolve())
    try:
        common = os.path.commonpath([real, allowed_dir])
    except ValueError as err:
        raise OSError(
            f"Refusing to write manifest outside snapshots directory: {real}\n"
            "Pass --allow-external to override."
        ) from err
    if common != allowed_dir:
        raise OSError(
            f"Refusing to write manifest outside snapshots directory: {real}\n"
            "Pass --allow-external to override."
        )


def validate_and_resolve(
    raw: str, allowed_base: Path | str, allow_external: bool
) -> str:
    """Validate and canonicalize a single path string against `allowed_base`.

    Kept at module-level to reduce the complexity of `main()` and allow
    easier testing.
    """
    if raw is None:
        return raw
    if "\x00" in raw:
        raise ValueError("Invalid path: contains null byte")
    try:
        normalized = os.path.normpath(raw)
    except (TypeError, ValueError) as err:
        logger.warning("Failed to normalize path %r: %s; falling back to raw", raw, err)
        normalized = raw
    except Exception:
        # Unexpected error while normalizing path: re-raise so callers can see it
        raise
    is_abs = os.path.isabs(raw)
    allowed_dir = str(allowed_base)
    if allow_external:
        return os.path.realpath(raw)
    if is_abs:
        real = os.path.realpath(raw)
        try:
            common = os.path.commonpath([real, allowed_dir])
        except ValueError as err:
            raise OSError(
                f"Refusing to use path outside snapshots directory: {real}\n"
                "Pass --allow-external to override."
            ) from err
        if common != allowed_dir:
            raise OSError(
                f"Refusing to use path outside snapshots directory: {real}\n"
                "Pass --allow-external to override."
            )
        return real
    else:
        if ".." in normalized.split(os.path.sep):
            raise OSError(
                f"Refusing to use path outside snapshots directory: {raw}\n"
                "Pass --allow-external to override."
            )
        return os.path.join(allowed_dir, normalized.lstrip(os.path.sep))


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate or generate snapshot checksums",
    )
    p.add_argument("--dir", type=str, default=None)
    p.add_argument("--manifest", type=str, default=None)
    p.add_argument(
        "--allow-external",
        action="store_true",
        help="Permite usar caminhos fora de snapshots/ (use com cuidado)",
    )
    p.add_argument("--update", action="store_true", help="Regenerate manifest")
    return p


def _remap_external_current(
    current: Dict[str, Dict[str, str]], allow_external: bool
) -> Dict[str, Dict[str, str]]:
    if not allow_external:
        return current

    remapped: Dict[str, Dict[str, str]] = {}
    orig_map: Dict[str, str] = {}
    collisions: Dict[str, list] = {}
    for k, v in current.items():
        # Use a safe basename to avoid path traversal characters in names
        if "\x00" in k:
            raise ValueError(
                "Invalid file path in current manifest: contains null byte"
            )
        name = os.path.basename(k)
        key = f"snapshots/{name}"
        if key in remapped:
            collisions.setdefault(key, [orig_map[key]]).append(k)
        else:
            remapped[key] = v
            orig_map[key] = k

    if collisions:
        _report_basename_collisions(collisions)
    return remapped


def _report_basename_collisions(collisions: Dict[str, List[str]]) -> NoReturn:
    """Reporta colisões de nomes base ao remapear caminhos externos.

    Parameters
    ----------
    collisions : Dict[str, List[str]]
        Mapeamento de chave remapeada (ex.: "snapshots/FILE") para a lista de
        paths originais que colidiram ao usar apenas o nome-base do arquivo.

    Raises
    ------
    SystemExit
        Sempre termina o processo com código de saída 3 quando colisões são
        detectadas, porque a operação não pode decidir qual arquivo preservar.
    """
    # Mensagens em PT-BR, quebradas em linhas curtas para ruff
    print(
        "Erro: nomes base duplicados detectados ao remapear",
        file=sys.stderr,
    )
    print("diretório externo:", file=sys.stderr)
    for key, paths in collisions.items():
        # imprimir fontes conflitantes de forma legível
        print(" -", key, "de:", ", ".join(paths), file=sys.stderr)
    print("Renomeie os arquivos ou execute sem", file=sys.stderr)
    print("--allow-external para evitar ambiguidade.", file=sys.stderr)
    raise SystemExit(3)


def main():
    args = _build_arg_parser().parse_args()

    # Resolve defaults and validate paths
    from src.paths import SNAPSHOTS_DIR as _SNAP

    allow_external = bool(args.allow_external)
    try:
        dir_str = validate_and_resolve(args.dir or str(_SNAP), _SNAP, allow_external)
        manifest_str = validate_and_resolve(
            args.manifest or str(_SNAP / "checksums.json"), _SNAP, allow_external
        )
    except (ValueError, OSError) as e:
        print(e)
        raise SystemExit(2) from e

    args.dir = Path(dir_str)
    args.manifest = Path(manifest_str)

    # Generate current manifest (CSV files only) and apply remapping logic
    current = generate_manifest(args.dir, pattern="*.csv")
    current = _remap_external_current(current, allow_external)

    if args.update:
        write_manifest(args.manifest, current, allow_external=allow_external)
        print(f"Manifest updated: {args.manifest}")
        return 0

    expected = load_manifest(args.manifest)

    ok, diffs = compare_manifests(expected, current)
    if ok:
        print("All snapshots match manifest.")
        return 0

    print("Snapshot validation failed. Differences:")
    for path, (exp, cur) in diffs.items():
        print(f" - {path}: expected={exp} current={cur}")

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
