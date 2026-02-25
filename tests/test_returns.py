import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd


def _count_returns(
    conn: sqlite3.Connection,
    ticker: str,
    return_type: str = "daily",
) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM returns WHERE ticker = ? AND return_type = ?",
        (ticker, return_type),
    )
    return cur.fetchone()[0]


def _fetch_returns_df(
    conn: sqlite3.Connection,
    ticker: str,
    return_type: str = "daily",
) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(
        "SELECT date, return FROM returns WHERE ticker = ?"
        " AND return_type = ? ORDER BY date",
        (ticker, return_type),
    )
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["date", "return"]) if rows else pd.DataFrame()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df.set_index("date")
    return df


def test_compute_returns_happy_path(sample_db):
    """Compute returns for sample ticker and verify rows written and numeric sanity."""
    import src.retorno as retorno

    ticker = "PETR4.SA"

    # Run compute_returns (should create `returns` table and insert rows)
    retorno.compute_returns(ticker, conn=sample_db)

    # Expect N-1 returns for N price rows in fixture
    cur = sample_db.cursor()
    cur.execute("SELECT COUNT(*) FROM prices WHERE ticker = ?", (ticker,))
    n_prices = cur.fetchone()[0]

    n_returns = _count_returns(sample_db, ticker)
    assert n_returns == max(0, n_prices - 1)

    # Numeric sanity: compare first return with pct_change computed locally
    # Load prices from DB to compute expected values
    df_prices = pd.read_sql_query(
        "SELECT date, close FROM prices WHERE ticker = ? ORDER BY date",
        sample_db,
        params=(ticker,),
        parse_dates=["date"],
    ).set_index("date")

    expected = df_prices["close"].pct_change().dropna()
    df_ret = _fetch_returns_df(sample_db, ticker)
    # Align indices and compare values vectorized to avoid loops in tests
    expected = expected.sort_index()
    df_ret = df_ret.sort_index()
    ret_vals = np.asarray(df_ret["return"].reindex(expected.index).values, dtype=float)
    exp_vals = np.asarray(expected.values, dtype=float)
    np.testing.assert_allclose(ret_vals, exp_vals, atol=1e-9, rtol=0)


def test_compute_returns_idempotent(sample_db):
    """Running compute_returns twice should not create duplicate rows."""
    import src.retorno as retorno

    ticker = "PETR4.SA"

    retorno.compute_returns(ticker, conn=sample_db)
    first_count = _count_returns(sample_db, ticker)

    # Run again
    retorno.compute_returns(ticker, conn=sample_db)
    second_count = _count_returns(sample_db, ticker)

    assert first_count == second_count


def test_compute_returns_range(sample_db):
    """compute_returns with start/end writes only rows within the requested range."""
    import src.retorno as retorno

    ticker = "PETR4.SA"

    # Choose a sub-range from fixtures (middle dates)
    start = datetime(2023, 1, 3)
    end = datetime(2023, 1, 5)

    retorno.compute_returns(ticker, start=start, end=end, conn=sample_db)

    df_ret = _fetch_returns_df(sample_db, ticker)
    assert not df_ret.empty
    assert df_ret.index.min() >= pd.to_datetime(start)
    assert df_ret.index.max() <= pd.to_datetime(end)


def test_write_returns_preserves_created_at_when_upsert_supported(sample_db):
    """Re-running compute_returns should preserve created_at timestamps."""
    import src.retorno as retorno

    ticker = "PETR4.SA"

    retorno.compute_returns(ticker, conn=sample_db)

    cur = sample_db.cursor()
    cur.execute(
        "SELECT created_at FROM returns WHERE ticker = ? ORDER BY date LIMIT 1",
        (ticker,),
    )
    first_created = cur.fetchone()[0]

    # Re-run and ensure created_at remains the same for existing rows
    retorno.compute_returns(ticker, conn=sample_db)
    cur.execute(
        "SELECT created_at FROM returns WHERE ticker = ? ORDER BY date LIMIT 1",
        (ticker,),
    )
    second_created = cur.fetchone()[0]

    assert first_created == second_created


def test_compute_returns_empty_and_single_price(sample_db):
    """Handle empty ticker (no prices) and single-price series gracefully."""
    import src.retorno as retorno

    # Empty ticker: should not raise and produce zero rows
    retorno.compute_returns("EMPTY_TICKER", conn=sample_db)
    # If `returns` table was never created (no prices), treat as zero rows.
    try:
        assert _count_returns(sample_db, "EMPTY_TICKER") == 0
    except sqlite3.OperationalError:
        # Table missing -> zero rows
        assert True

    # Single price row: insert one price and expect zero returns
    cur = sample_db.cursor()
    cur.execute(
        "INSERT INTO prices (ticker,date,open,high,low,close,volume,source) VALUES (?,?,?,?,?,?,?,?)",
        ("SINGLE", "2023-01-01", 100.0, 100.0, 100.0, 100.0, 100, "fixture"),
    )
    sample_db.commit()

    retorno.compute_returns("SINGLE", conn=sample_db)
    try:
        assert _count_returns(sample_db, "SINGLE") == 0
    except sqlite3.OperationalError:
        # Table missing -> zero rows
        assert True
