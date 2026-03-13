#!/usr/bin/env python3
"""CI checksum validation script for snapshot integrity.

Validates snapshot checksums against stored metadata in DB.

Usage:
    python scripts/ci_validate_checksums.py

Exit codes:
    0: All checksums valid
    1: Validation failures detected
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path for imports
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src import db  # noqa: E402
from src.utils.checksums import sha256_file  # noqa: E402


def main() -> int:  # noqa: C901 - complexity acceptable in simple script
    """Run checksum validation against all non-archived snapshots.

    Returns
    -------
    int
        Exit code: 0 if all pass, 1 if any fail.
    """
    print("Validating snapshot checksums...")
    print()

    db_path = os.environ.get("DB_PATH", "dados/data.db")
    conn = None
    try:
        conn = db.connect(db_path=db_path)
        snapshots = db.list_snapshots(archived=False, conn=conn)
    except Exception as exc:  # pragma: no cover - defensive
        # report a clear message and exit non-zero
        print(
            f"Error accessing database at {db_path}: {exc}",
            file=sys.stderr,
        )
        if conn:
            try:
                conn.close()
            except Exception:  # pragma: no cover - best effort
                pass
        sys.exit(1)
    finally:
        if conn:
            conn.close()

    if not snapshots:
        print("No snapshots to validate")
        return 0

    total = 0
    passed = 0
    failed = 0
    missing = 0

    for snap in snapshots:
        snap_id = snap.get("id")
        ticker = snap.get("ticker")
        snapshot_path = snap.get("snapshot_path")
        stored_checksum = snap.get("checksum")

        if not snapshot_path or not stored_checksum:
            # Skip snapshots without path or checksum metadata
            continue

        total += 1

        path_obj = Path(snapshot_path)
        if not path_obj.exists():
            print(f"FAIL: {ticker} (id={snap_id}) - File not found at {snapshot_path}")
            missing += 1
            failed += 1
            continue

        computed = sha256_file(path_obj)
        if computed == stored_checksum:
            print(f"PASS: {ticker} (id={snap_id}) - checksum: {computed[:12]}...")
            passed += 1
        else:
            print(f"FAIL: {ticker} (id={snap_id}) - Checksum mismatch")
            print(f"  Expected: {stored_checksum}")
            print(f"  Computed: {computed}")
            failed += 1

    print()
    print("Summary:")
    print(f"- Total: {total}")
    print(f"- Passed: {passed}")
    print(f"- Failed: {failed}")
    print(f"- Missing: {missing}")
    print()

    if failed > 0:
        print("Exit code: 1")
        return 1

    print("Exit code: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
