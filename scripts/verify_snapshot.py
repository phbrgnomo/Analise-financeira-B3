#!/usr/bin/env python3
"""Wrapper CLI to validate snapshots using scripts/validate_snapshots.py.

This small script forwards args to the existing validation script and returns
its exit code. It simplifies CI step commands and makes intent explicit.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    repo_root = Path(__file__).resolve().parent
    validate = repo_root / "validate_snapshots.py"
    # Fallback if script is in scripts/ and we run from project root
    if not validate.exists():
        validate = repo_root.parent / "scripts" / "validate_snapshots.py"

    if not validate.exists():
        print("Error: scripts/validate_snapshots.py not found", file=sys.stderr)
        return 2

    cmd = [sys.executable, str(validate)] + list(argv)
    try:
        # Use subprocess.run with a list of arguments and shell=False to avoid
        # shell interpretation of user-provided input (mitigates CWE-78).
        proc = subprocess.run(cmd, shell=False)
        return proc.returncode
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Error running validation: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
