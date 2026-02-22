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
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from pathlib import Path as _Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Ensure repo root is on sys.path so `from src...` imports work when the
# script is executed directly (e.g. `python scripts/validate_snapshots.py`).
# scripts/ is at repo_root/scripts, so repo_root is two parents up from here.
_REPO_ROOT = _Path(__file__).resolve().parent.parent
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
    # Validate target path to avoid path traversal from untrusted inputs
    # only when called from the CLI with `allow_external=False`.
    if not allow_external:
        _extracted_from_write_manifest_7(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        # Use timezone-aware UTC datetime to avoid DeprecationWarning on Python 3.12+
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": manifest,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# TODO Rename this here and in `write_manifest`
def _extracted_from_write_manifest_7(path):
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
    if not allow_external:
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
    else:
        return os.path.realpath(raw)


def main():
    p = argparse.ArgumentParser(description="Validate or generate snapshot checksums")
    p.add_argument("--dir", type=str, default=None)
    p.add_argument("--manifest", type=str, default=None)
    p.add_argument(
        "--allow-external",
        action="store_true",
        help="Permite usar caminhos fora de snapshots/ (use com cuidado)",
    )
    p.add_argument("--update", action="store_true", help="Regenerate manifest")
    args = p.parse_args()

    # Resolve defaults from `src.paths` only after sys.path has been updated
    # so running the script directly works in CI and locally.
    if args.dir is None or args.manifest is None:
        from src.paths import SNAPSHOTS_DIR as _SNAP

        if args.dir is None:
            args.dir = str(_SNAP)
        if args.manifest is None:
            args.manifest = str(_SNAP / "checksums.json")

    # Validate and canonicalize user-provided paths before creating Path objects
    allow_external = bool(args.allow_external)

    # validate_and_resolve moved to module-level to reduce complexity of `main()`
    from src.paths import SNAPSHOTS_DIR as _SNAP

    try:
        dir_str = validate_and_resolve(args.dir, _SNAP, allow_external)
        manifest_str = validate_and_resolve(args.manifest, _SNAP, allow_external)
    except (ValueError, OSError) as e:
        print(e)
        raise SystemExit(2) from e

    args.dir = Path(dir_str)
    args.manifest = Path(manifest_str)

    # For validation we only consider CSV snapshot files; keep the helper
    # flexible so tests or other callers can request different patterns.
    current = generate_manifest(args.dir, pattern="*.csv")

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
