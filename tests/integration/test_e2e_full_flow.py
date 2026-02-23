import json

import pandas as pd

from src import db as src_db
from src.ingest import pipeline
from src.ingest.runner import run_write_with_validation


def test_e2e_full_flow(tmp_path):
    # prepare DB
    db_file = tmp_path / "dados" / "data.db"
    src_db.create_tables_if_not_exists(db_path=str(db_file))

    # create a simple canonical dataframe expected by validator/persistence
    df = pd.DataFrame(
        {
            "date": ["2021-01-01", "2021-01-02"],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [10.2, 11.2],
            "volume": [100, 150],
            "source": ["test", "test"],
        }
    )

    metadata_path = tmp_path / "metadata.json"

    # save raw CSV (this will also create metadata JSON with per-row checksums)
    save_meta = pipeline.save_raw_csv(
        df,
        provider="testprov",
        ticker="TST",
        ts="202101",
        raw_root=tmp_path / "raw",
        db_path=str(db_file),
        metadata_path=str(metadata_path),
    )

    assert save_meta.get("status") == "success"

    # Map to canonical schema first (runner expects canonical DataFrame)
    from src.etl.mapper import to_canonical

    canonical = to_canonical(
        df,
        provider_name="testprov",
        ticker="TST",
        raw_checksum=save_meta.get("raw_checksum"),
        fetched_at=save_meta.get("fetched_at"),
    )

    # run validation + write using the runner
    valid_df, invalid_df, summary, details = run_write_with_validation(
        canonical,
        provider="testprov",
        ticker="TST",
        raw_file=save_meta.get("filepath") or "",
        ts=save_meta.get("fetched_at") or "",
        raw_root=str(tmp_path / "raw"),
        metadata_path=str(metadata_path),
        threshold=None,
        abort_on_exceed=True,
        persist_invalid=False,
        db_path=str(db_file),
    )

    # ensure rows were written to DB
    res_df = src_db.read_prices("TST", engine=None, db_path=str(db_file))
    assert not res_df.empty
    assert len(res_df) == len(valid_df)

    # metadata JSON should include per_row_checksums
    with open(str(metadata_path), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, list)
    # latest entry should include per_row_checksums
    assert any("per_row_checksums" in e for e in data)
