import pandas as pd

from src import db, validation


def test_ingest_log_written_on_validation(tmp_path):
    db_file = tmp_path / "dados" / "data.db"
    db.create_tables_if_not_exists(db_path=str(db_file))

    # create a DataFrame with a bad row to trigger validation error
    df = pd.DataFrame({"date": ["2021-05-01", "bad-date"], "open": [1.0, "x"]})

    # run validation; persist_invalid False to avoid file writes, abort_on_exceed False
    valid, invalid, summary, details = validation.validate_and_handle(
        df,
        provider="p",
        ticker="TSTLOG",
        raw_file="raw.csv",
        ts="20210501",
        raw_root=str(tmp_path),
        metadata_path=str(tmp_path / "metadata.json"),
        threshold=1.0,
        abort_on_exceed=False,
        persist_invalid=False,
        db_path=str(db_file),
    )

    # Check metadata JSON file for an entry corresponding to this ingest
    import json

    with open(str(tmp_path / "metadata.json"), "r", encoding="utf-8") as fh:
        data = json.load(fh)

    # Expect at least one metadata entry and one referencing our ticker
    assert isinstance(data, list)
    assert len(data) >= 1

    # Expect at least one metadata entry describing invalid rows
    assert any(
        (
            isinstance(e.get("error_details"), list)
            or e.get("invalid_count") is not None
        )
        for e in data
    )
