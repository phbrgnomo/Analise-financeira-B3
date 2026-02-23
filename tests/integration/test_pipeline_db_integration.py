from pathlib import Path

import pandas as pd

from src import db
from src.etl.mapper import to_canonical
from src.ingest.pipeline import save_raw_csv


def test_pipeline_end_to_end(tmp_path):
    # load sample CSV
    sample_path = Path(__file__).resolve().parents[1] / "fixtures" / "sample_ticker.csv"
    df = pd.read_csv(sample_path, parse_dates=["date"])

    # save raw CSV and metadata to temporary dirs
    raw_root = tmp_path / "raw"
    metadata_path = tmp_path / "metadata" / "ingest_logs.json"
    meta = save_raw_csv(
        df,
        "yfinance",
        "PETR4.SA",
        ts="20230101T000000Z",
        raw_root=raw_root,
        metadata_path=metadata_path,
    )
    assert meta.get("status") == "success"

    # map to canonical
    canonical = to_canonical(
        df,
        provider_name="yfinance",
        ticker="PETR4.SA",
        raw_checksum=meta.get("raw_checksum"),
        fetched_at=meta.get("fetched_at"),
    )
    assert not canonical.empty

    # initialize DB in tmp and write canonical rows
    db_path = str(tmp_path / "dados" / "data.db")
    db.init_db(db_path)
    db.write_prices(canonical, "PETR4.SA", db_path=db_path)

    # read back and verify
    out = db.read_prices("PETR4.SA", conn=None, db_path=db_path)
    assert len(out) == len(canonical)

    # verify metadata JSONL exists
    jsonl = Path(metadata_path).with_suffix(".jsonl")
    assert jsonl.exists()
    content = jsonl.read_text()
    assert "raw_checksum" in content
