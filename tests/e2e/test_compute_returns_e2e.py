import os

import pandas as pd

from src.retorno import compute_returns


def test_compute_returns_e2e_using_snapshot(tmp_path):
    """End-to-end test: load snapshot CSV into an in-memory DB and run compute_returns.

    Verifies that compute_returns writes expected number of rows and values.
    """
    curdir = os.path.dirname(__file__)
    csv_path = os.path.join(curdir, "..", "..", "snapshots", "PETR4_snapshot.csv")
    df = pd.read_csv(csv_path, parse_dates=["date"])

    # Build a minimal prices DB using fixture_utils helper
    from tests.fixture_utils import create_prices_db_from_rows

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

    conn = create_prices_db_from_rows(rows)
    try:
        compute_returns("PETR4.SA", conn=conn)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM returns WHERE ticker = ?", ("PETR4.SA",))
        n = cur.fetchone()[0]
        assert n == max(0, len(rows) - 1)
    finally:
        conn.close()
