import sqlite3
import threading
import time

import pandas as pd

from src import db


def make_df():
    return pd.DataFrame(
        [
            {
                "date": "2021-04-01",
                "open": 30.0,
                "high": 31.0,
                "low": 29.5,
                "close": 30.5,
                "volume": 300,
                "source": "r",
                "fetched_at": "2021-04-01T12:00:00Z",
            }
        ]
    )


def _hold_lock(db_path, hold_seconds=0.5):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # start a transaction that keeps DB locked
    cur.execute("BEGIN EXCLUSIVE")
    time.sleep(hold_seconds)
    conn.rollback()
    conn.close()


def test_write_with_retry_on_busy(tmp_path):
    db_file = tmp_path / "dados" / "data.db"
    db.create_tables_if_not_exists(db_path=str(db_file))

    # start thread that holds an exclusive lock for a short period
    t = threading.Thread(target=_hold_lock, args=(str(db_file), 0.6))
    t.start()

    # wait a bit to ensure lock acquired
    time.sleep(0.05)

    # perform write which should encounter busy and retry until lock released
    df = make_df()
    db.write_prices(df, "TLOCK", db_path=str(db_file))

    t.join()

    # verify row was written
    out = db.read_prices("TLOCK", db_path=str(db_file))
    assert not out.empty
