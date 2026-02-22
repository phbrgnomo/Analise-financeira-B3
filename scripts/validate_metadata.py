#!/usr/bin/env python3
"""Valida um arquivo de metadados JSON contra o schema em docs/metadata_schema.json

Uso:
    python3 scripts/validate_metadata.py path/to/metadata.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import ValidationError, validate


def load_schema():
    path = Path(__file__).resolve().parents[1] / "docs" / "metadata_schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_metadata(path: Path):
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/validate_metadata.py path/to/metadata.json")
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(2)

    schema = load_schema()
    try:
        data = load_metadata(path)
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
