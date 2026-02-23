import pandas as pd

from src import db


def make_df():
    return pd.DataFrame(
        [
            {
                "date": "2021-02-01",
                "open": 20.0,
                "high": 21.0,
                "low": 19.5,
                "close": 20.5,
                "volume": 200,
                "source": "s",
                "fetched_at": "2021-02-01T12:00:00Z",
            }
        ]
    )


def test_on_conflict_where_skips_update_when_checksum_same(tmp_path, monkeypatch):
    db_file = tmp_path / "dados" / "data.db"
    # force preferred path (new sqlite) to ensure ON CONFLICT used
    monkeypatch.setattr(db, "_sqlite_runtime_version", lambda engine: (3, 45, 0))

    df = make_df()
    ticker = "TST2"

    # prepare DB and first insert
    db.create_tables_if_not_exists(db_path=str(db_file))
    db.write_prices(df, ticker, db_path=str(db_file))
    first = db.read_prices(ticker, engine=None, db_path=str(db_file))
    assert not first.empty
    fa1 = first.iloc[0]["fetched_at"]

    # second write with identical payload but different fetched_at
    df2 = make_df()
    df2.at[0, "fetched_at"] = "2021-02-01T13:00:00Z"
    db.write_prices(df2, ticker, db_path=str(db_file))

    second = db.read_prices(ticker, engine=None, db_path=str(db_file))
    fa2 = second.iloc[0]["fetched_at"]

    # Because checksum is same, ON CONFLICT ... WHERE should skip update
    assert fa1 == fa2
