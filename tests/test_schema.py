import csv
import json
import re
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_schema():
    root = _project_root()
    schema_path = root / "docs" / "schema.json"
    return json.loads(schema_path.read_text())


def _schema_columns():
    schema = _load_schema()
    cols = []
    for col in schema.get("columns", []):
        if isinstance(col, dict) and "name" in col:
            cols.append(col["name"])
        else:
            cols.append(col)
    return cols


def test_example_matches_schema_header():
    root = _project_root()
    example_path = root / "dados" / "samples" / "ticker_example.csv"
    expected = _schema_columns()
    with example_path.open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == expected


def test_example_matches_schema():
    root = Path(__file__).resolve().parent.parent
    schema_path = root / "docs" / "schema.json"
    example_path = root / "dados" / "samples" / "ticker_example.csv"

    schema = json.loads(schema_path.read_text())
    assert schema.get("schema_version") == 1
    columns = [c["name"] for c in schema["columns"]]

    with example_path.open() as f:
        reader = csv.DictReader(f)
        # Ensure header matches schema column order
        assert reader.fieldnames == columns
        rows = list(reader)

    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    hex_re = re.compile(r"^[0-9a-f]{64}$")

    for r in rows:
        if not date_re.match(r["date"]):
            raise AssertionError(f"date invalid: {r['date']}")
        if not iso_re.match(r["fetched_at"]):
            raise AssertionError(f"fetched_at invalid: {r['fetched_at']}")
        if not hex_re.match(r["raw_checksum"]):
            raise AssertionError(f"raw_checksum invalid: {r['raw_checksum']}")
