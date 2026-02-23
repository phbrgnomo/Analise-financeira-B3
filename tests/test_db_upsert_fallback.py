import pandas as pd

from src import db


def make_df():
    return pd.DataFrame(
        [
            {
                "date": "2021-01-01",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 100,
                "source": "x",
                "fetched_at": "2021-01-01T12:00:00Z",
            }
        ]
    )


def test_upsert_fallback_preserves_fetched_at(tmp_path, monkeypatch):
    db_file = tmp_path / "dados" / "data.db"
    # force fallback by monkeypatching runtime detector
    monkeypatch.setattr(db, "_sqlite_runtime_version", lambda engine: (3, 22, 0))

    df = make_df()
    ticker = "TST"

    # prepare DB schema and first write: creates row
    db.create_tables_if_not_exists(db_path=str(db_file))
    db.write_prices(df, ticker, db_path=str(db_file))

    # capture fetched_at after first write
    first = db.read_prices(ticker, engine=None, db_path=str(db_file))
    assert not first.empty
    fa1 = first.iloc[0]["fetched_at"]

    # second write with identical content (checksum same) but different fetched_at
    df2 = make_df()
    df2.at[0, "fetched_at"] = "2021-01-01T13:00:00Z"
    db.write_prices(df2, ticker, db_path=str(db_file))

    second = db.read_prices(ticker, engine=None, db_path=str(db_file))
    fa2 = second.iloc[0]["fetched_at"]

    # checksum equal: fallback should have skipped update and preserved fetched_at
    assert fa1 == fa2
