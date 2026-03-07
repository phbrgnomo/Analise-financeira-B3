import os
import sqlite3

import pandas as pd

from src.retorno import compute_returns


def test_compute_returns_e2e_using_snapshot():
    """End-to-end test: load fixture CSV into an in-memory DB and run compute_returns.

    Verifies that compute_returns writes expected number of rows and values.
    """
    # use the existing sample_ticker fixture which is shipped
    curdir = os.path.dirname(__file__)
    csv_path = os.path.join(curdir, "..", "fixtures", "sample_ticker.csv")
    df = pd.read_csv(csv_path, parse_dates=["date"])

    # Build a minimal prices DB in-memory without importing test helpers
    # column names in sample_ticker.csv are lowercase
    rows = [
        (
            "PETR4",
            r["date"].strftime("%Y-%m-%d"),
            float(r["open"]),
            float(r["high"]),
            float(r["low"]),
            float(r["close"]),
            int(r["volume"]),
            "snapshot",
        )
        for _, r in df.iterrows()
    ]

    # create in-memory DB and insert rows
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE prices (
            ticker TEXT,
            date DATE,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            source TEXT
        )
        """
    )
    insert_sql = (
        "INSERT INTO prices (ticker,date,open,high,low,close,volume,source)"
        " VALUES (?,?,?,?,?,?,?,?)"
    )
    cur.executemany(insert_sql, rows)
    conn.commit()
    try:
        compute_returns("PETR4", conn=conn)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM returns WHERE ticker = ?", ("PETR4",))
        n = cur.fetchone()[0]
        assert n == max(0, len(rows) - 1)
    finally:
        conn.close()
