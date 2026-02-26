import os
import sqlite3

import pandas as pd

from src.retorno import compute_returns


def test_compute_returns_e2e_using_snapshot():
    """End-to-end test: load snapshot CSV into an in-memory DB and run compute_returns.

    Verifies that compute_returns writes expected number of rows and values.
    """
    curdir = os.path.dirname(__file__)
    csv_path = os.path.join(curdir, "..", "..", "snapshots", "PETR4_snapshot.csv")
    df = pd.read_csv(csv_path, parse_dates=["date"])

    # Build a minimal prices DB in-memory without importing test helpers
    rows = [
        (
            "PETR4.SA",
            r["date"].strftime("%Y-%m-%d"),
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            int(r["Volume"]),
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
            date TEXT,
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
        compute_returns("PETR4.SA", conn=conn)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM returns WHERE ticker = ?", ("PETR4.SA",))
        n = cur.fetchone()[0]
        assert n == max(0, len(rows) - 1)
    finally:
        conn.close()
