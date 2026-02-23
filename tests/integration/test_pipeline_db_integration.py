import json

import pandas as pd

from src import db
from src.etl.mapper import to_canonical
from src.ingest.pipeline import save_raw_csv


def test_pipeline_write_and_read_prices(tmp_path):
    # Prepare small DF
    df = pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Adj Close": [10.5, 11.5],
            "Volume": [100, 200],
        },
        index=pd.date_range("2026-02-01", periods=2, freq="D"),
    )

    raw_root = tmp_path / "raw"
    metadata_path = tmp_path / "metadata" / "ingest_logs.jsonl"

    # Save raw CSV and metadata
    meta = save_raw_csv(
        df,
        "testprov",
        "TICK",
        raw_root=raw_root,
        metadata_path=metadata_path,
    )

    assert meta["status"] == "success"

    # Map to canonical
    canonical = to_canonical(
        df,
        provider_name="testprov",
        ticker="TICK",
        raw_checksum=meta["raw_checksum"],
        fetched_at=meta["fetched_at"],
    )

    # Init DB at tmp path
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))

    # Write canonical rows
    db.write_prices(canonical, "TICK", db_path=str(db_path))

    # Read back
    out = db.read_prices("TICK", conn=None, db_path=str(db_path))
    assert not out.empty
    assert len(out) == len(canonical)

    # Verify metadata JSONL contains the ingest entry
    text = metadata_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    entries = [json.loads(line) for line in lines]
    found = [
        e
        for e in entries
        if e.get("raw_checksum") == meta.get("raw_checksum")
    ]
    assert len(found) >= 1
