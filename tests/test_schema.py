import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_schema() -> Dict[str, Any]:
    """Load and parse the project schema JSON.

    Returns a dict representation of `docs/schema.json`.
    """
    root = _project_root()
    schema_path = root / "docs" / "schema.json"
    return json.loads(schema_path.read_text())


def _schema_columns() -> List[str]:
    """Return the ordered list of column names from the schema.

    Extracts `name` from column dicts when present, preserving order.
    """
    schema = _load_schema()
    cols: List[str] = []
    for col in schema.get("columns", []):
        if isinstance(col, dict) and "name" in col:
            cols.append(col["name"])
        else:
            cols.append(col)
    return cols


def test_example_matches_schema_header() -> None:
    root = _project_root()
    example_path = root / "dados" / "samples" / "ticker_example.csv"
    expected = _schema_columns()
    with example_path.open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    """Afirma que o cabeçalho do exemplo corresponde à ordem de colunas do schema."""

    assert header == expected


def test_example_matches_schema() -> None:
    root = Path(__file__).resolve().parent.parent
    schema_path = root / "docs" / "schema.json"
    example_path = root / "dados" / "samples" / "ticker_example.csv"

    schema = json.loads(schema_path.read_text())
    """Valida o conteúdo de `ticker_example.csv` contra `docs/schema.json`.

    Verifica `schema_version`, cabeçalho, formatos de data/iso/checksum e
    falha claramente quando alguma validação não passa.
    """

    # Accept any positive integer schema_version to remain resilient to bumps
    sv = schema.get("schema_version")
    assert isinstance(sv, int) and sv >= 1
    columns = [c["name"] for c in schema["columns"]]

    with example_path.open() as f:
        reader = csv.DictReader(f)
        # Ensure header matches schema column order
        assert reader.fieldnames == columns
        rows = list(reader)

    # Fail early if there are no data rows in the example CSV
    assert rows, "no data rows in ticker_example.csv"

    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    hex_re = re.compile(r"^[0-9a-f]{64}$")

    # Locate the first invalid row for each check and fail with a clear message.
    bad = next((r for r in rows if not date_re.match(r["date"])), None)
    assert bad is None, f"date invalid: {bad['date']}"

    bad = next((r for r in rows if not iso_re.match(r["fetched_at"])), None)
    assert bad is None, f"fetched_at invalid: {bad['fetched_at']}"

    bad = next((r for r in rows if not hex_re.match(r["raw_checksum"])), None)
    assert bad is None, f"raw_checksum invalid: {bad['raw_checksum']}"
