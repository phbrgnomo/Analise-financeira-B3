import datetime

import pandas as pd
from sqlalchemy import text

from src import db


def _sample_df():
    return pd.DataFrame(
        [
            {
                "date": "2021-01-01",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 100,
            },
            {
                "date": "2021-01-02",
                "open": 11,
                "high": 12,
                "low": 10,
                "close": 11.5,
                "volume": 200,
            },
            {
                "date": "2021-01-03",
                "open": 12,
                "high": 13,
                "low": 11,
                "close": 12.5,
                "volume": 300,
            },
        ]
    )


def test_read_prices_filters(tmp_path):
    # Use a file-backed DB to exercise on-disk behavior
    db_path = str(tmp_path / "data.db")
    eng = db._get_engine(None, db_path)
    db.create_tables_if_not_exists(engine=eng)

    df = _sample_df()
    # write all rows
    db.write_prices(df, "TEST", engine=eng)

    # start filter should exclude first row
    df_start = db.read_prices("TEST", start="2021-01-02", engine=eng)
    assert list(df_start["date"]) == [
        datetime.date(2021, 1, 2),
        datetime.date(2021, 1, 3),
    ]

    # end filter should exclude last row
    df_end = db.read_prices("TEST", end="2021-01-02", engine=eng)
    assert list(df_end["date"]) == [
        datetime.date(2021, 1, 1),
        datetime.date(2021, 1, 2),
    ]


def test_create_and_detect_index_on_date(tmp_path):
    db_path = str(tmp_path / "data.db")
    eng = db._get_engine(None, db_path)
    db.create_tables_if_not_exists(engine=eng)

    # create index on date column
    with eng.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date)"))

    # query sqlite_master to ensure index exists
    with eng.connect() as conn:
        res = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_prices_date'"
            )
        )
        rows = res.fetchall()

    assert len(rows) == 1
