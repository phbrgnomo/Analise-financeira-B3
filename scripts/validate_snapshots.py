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
import sys
from datetime import datetime, timezone
from pathlib import Path
from pathlib import Path as _Path
from typing import Any, Dict, Tuple, cast

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


def load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def write_manifest(path: Path, manifest: Dict[str, Dict[str, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        # Use timezone-aware UTC datetime to avoid DeprecationWarning on Python 3.12+
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": manifest,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def main():
    p = argparse.ArgumentParser(description="Validate or generate snapshot checksums")
    p.add_argument("--dir", type=Path, default=None)
    p.add_argument("--manifest", type=Path, default=None)
    p.add_argument("--update", action="store_true", help="Regenerate manifest")
    args = p.parse_args()

    # Resolve defaults from `src.paths` only after sys.path has been updated
    # so running the script directly works in CI and locally.
    if args.dir is None or args.manifest is None:
        from src.paths import SNAPSHOTS_DIR as _SNAP
        if args.dir is None:
            args.dir = _SNAP
        if args.manifest is None:
            args.manifest = _SNAP / "checksums.json"

    # For validation we only consider CSV snapshot files; keep the helper
    # flexible so tests or other callers can request different patterns.
    current = generate_manifest(args.dir, pattern="*.csv")

    if args.update:
        write_manifest(args.manifest, current)
        print(f"Manifest updated: {args.manifest}")
        return 0

    expected_payload = load_manifest(args.manifest)
    expected_raw = expected_payload.get("files") if expected_payload else {}

    expected: Dict[str, Dict[str, str]] = cast(
        Dict[str, Dict[str, str]], expected_raw or {}
    )

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
