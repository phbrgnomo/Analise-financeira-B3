#!/usr/bin/env python3
"""Valida um arquivo de metadados JSON contra o schema em docs/metadata_schema.json

Uso:
    python3 scripts/validate_metadata.py path/to/metadata.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate


def load_schema():
    path = Path(__file__).resolve().parents[1] / "docs" / "metadata_schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_metadata(path: str) -> dict[str, Any]:
    """Load JSON metadata from a pre-validated canonical path.

    Parameters
    ----------
    path : str
        A validated, canonical filesystem path to a JSON metadata file. The
        caller must ensure `path` is safe (no untrusted Path construction).

    Returns
    -------
    dict[str, Any]
        Parsed JSON object as a Python dictionary.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at `path`.
    json.JSONDecodeError
        If the file contents are not valid JSON.
    """
    # `path` must be a validated, canonical string (no untrusted Path construction)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extra_checks(data: dict):
    errors = []
    # checksum length
    checksum = data.get("checksum")
    if checksum and len(checksum) != 64:
        errors.append(f"checksum length is {len(checksum)} but must be 64 hex chars")
    if sd := data.get("snapshot_date"):
        try:
            datetime.strptime(sd, "%Y-%m-%d")
        except Exception as e:
            errors.append(f"snapshot_date parse error: {e}")
    # rows
    rows = data.get("rows")
    if rows is not None and (not isinstance(rows, int) or rows < 0):
        errors.append("rows must be non-negative integer")
    return errors


def main():  # noqa: C901
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/validate_metadata.py path/to/metadata.json")
        sys.exit(2)

    # Read raw CLI input as string and validate before any Path construction
    raw = sys.argv[1]
    # Resolve path and protect against path traversal by default: only allow
    # metadata files inside the repository. Pass --allow-external to override.
    allow_external = "--allow-external" in sys.argv

    if "\x00" in raw:
        print("Invalid path: contains null byte")
        sys.exit(2)

    normalized = os.path.normpath(raw)

    is_abs = os.path.isabs(raw)

    repo_root = Path(__file__).resolve().parents[1]
    allowed_dir = str(repo_root)

    if allow_external:
        # allow external: canonicalize
        resolved = os.path.realpath(raw)

    elif is_abs:
        real = os.path.realpath(raw)
        try:
            common = os.path.commonpath([real, allowed_dir])
        except ValueError:
            print(
                f"Refusing to validate file outside repository root: {real}\n"
                "Pass --allow-external to override (use with caution)."
            )
            sys.exit(2)
        if common != allowed_dir:
            print(
                f"Refusing to validate file outside repository root: {real}\n"
                "Pass --allow-external to override (use with caution)."
            )
            sys.exit(2)
        resolved = real
    else:
        # relative: disallow traversal
        if ".." in normalized.split(os.path.sep):
            print(
                f"Refusing to validate file outside repository root: {raw}\n"
                "Pass --allow-external to override (use with caution)."
            )
            sys.exit(2)
        resolved = os.path.join(allowed_dir, normalized.lstrip(os.path.sep))
    if not os.path.exists(resolved):
        print(f"File not found: {resolved}")
        sys.exit(2)

    schema = load_schema()
    try:
        data = load_metadata(resolved)
    except Exception as e:
        print(f"Failed to load JSON: {e}")
        sys.exit(2)

    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        print("JSON Schema validation failed:")
        print(e.message)
        sys.exit(1)

    if extras := extra_checks(data):
        print("Extra validation errors:")
        for e in extras:
            print(" - ", e)
        sys.exit(1)

    print("OK: metadata is valid")


if __name__ == "__main__":
    main()
