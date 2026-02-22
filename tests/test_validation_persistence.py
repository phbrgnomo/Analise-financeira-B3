import json
from pathlib import Path

import pandas as pd

from src.validation import validate_and_handle


def test_persist_and_log_invalid_rows(tmp_path):
    """Valida que linhas inválidas são persistidas e registradas em ingest_logs."""
    # Arrange
    rows = {
        "ticker": ["PETR4.SA"] * 3,
        "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
        "open": [100.0, 101.0, 102.0],
        "high": [99.0, 106.0, 107.0],  # first row violates high > low
        "low": [105.0, 100.0, 101.0],
        "close": [104.0, 105.0, 106.0],
        "volume": [1000000, 1100000, 1200000],
        "source": ["yfinance"] * 3,
        "fetched_at": ["2026-01-01T12:00:00Z"] * 3,
        "raw_checksum": ["abc123"] * 3,
    }

    df = pd.DataFrame(rows)

    metadata_path = tmp_path / "ingest_logs.json"
    raw_root = tmp_path / "raw"

    # Act
    valid_df, invalid_df, summary, details = validate_and_handle(
        df=df,
        provider="yfinance",
        ticker="PETR4.SA",
        raw_file="sample.csv",
        ts="2026-02-21T00:00:00Z",
        raw_root=str(raw_root),
        metadata_path=str(metadata_path),
        threshold=1.0,  # high threshold so we don't abort
        abort_on_exceed=False,
        persist_invalid=True,
    )

    # Assert: invalid row detected
    assert len(invalid_df) >= 1

    # Assert: invalid CSV file created and path recorded in ingest log entry
    assert "ingest_log_entry" in details
    entry = details["ingest_log_entry"]
    invalid_filepath = entry.get("invalid_filepath")
    assert invalid_filepath and Path(invalid_filepath).exists()

    # Assert: metadata file contains the entry
    assert metadata_path.exists()
    with open(metadata_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    assert isinstance(data, list) and len(data) >= 1
    recorded = data[-1]
    assert recorded["provider"] == "yfinance"
    assert recorded["ticker"] == "PETR4.SA"
    assert recorded["invalid_count"] == len(details.get("error_records", []))
