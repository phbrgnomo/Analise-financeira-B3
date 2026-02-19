import csv
import json
import re
from pathlib import Path


def test_example_matches_schema():
    root = Path(__file__).resolve().parent.parent
    schema_path = root / 'docs' / 'schema.yaml'
    example_path = root / 'dados' / 'examples' / 'ticker_example.csv'

    schema = json.loads(schema_path.read_text())
    assert schema.get('schema_version') == 1
    columns = [c['name'] for c in schema['columns']]

    with example_path.open() as f:
        reader = csv.DictReader(f)
        # Ensure header matches schema column order
        assert reader.fieldnames == columns
        rows = list(reader)

    date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    iso_re = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
    hex_re = re.compile(r'^[0-9a-f]{64}$')

    for r in rows:
        assert date_re.match(r['date']), f"date invalid: {r['date']}"
        assert iso_re.match(r['fetched_at']), f"fetched_at invalid: {r['fetched_at']}"
        hex_match = hex_re.match(r['raw_checksum'])
        assert hex_match, f"raw_checksum invalid: {r['raw_checksum']}"
