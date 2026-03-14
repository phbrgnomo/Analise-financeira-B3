import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.tickers import normalize_b3_ticker


def _count_returns(
    conn: sqlite3.Connection,
    ticker: str,
    return_type: str = "daily",
) -> int:
    """Return the number of return rows for a ticker and return type.

    Counts rows in the `returns` table for the given `ticker` and `return_type`.

    Args:
        conn (sqlite3.Connection): database connection.
        ticker (str): ticker symbol.
        return_type (str): return period/type (default 'daily').

    Returns:
        int: number of matching return rows.
    """
    ticker = normalize_b3_ticker(ticker)
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
    """Fetch returns for a ticker as a pandas DataFrame.

    Retrieves rows from the `returns` table for `ticker` and `return_type`,
    parses the `date` column as datetimes, normalizes timezone information
    (drops tz), and sets `date` as the DataFrame index.

    Args:
        conn (sqlite3.Connection): database connection.
        ticker (str): ticker symbol.
        return_type (str): return period/type (default 'daily').

    Returns:
        pandas.DataFrame: DataFrame indexed by date with a `return` column;
        may be empty if no rows are found.
    """
    ticker = normalize_b3_ticker(ticker)
    cur = conn.cursor()
    cur.execute(
        "SELECT date, return_value AS return FROM returns WHERE ticker = ?"
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

    ticker = "PETR4"

    # Run compute_returns (should create `returns` table and insert rows)
    retorno.compute_returns(ticker, conn=sample_db)

    # Expect N-1 returns for N price rows in fixture
    cur = sample_db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM prices WHERE ticker = ?",
        (normalize_b3_ticker(ticker),),
    )
    n_prices = cur.fetchone()[0]

    n_returns = _count_returns(sample_db, ticker)
    assert n_returns == max(0, n_prices - 1)

    # Numeric sanity: compare first return with pct_change computed locally
    # Load prices from DB to compute expected values
    df_prices = pd.read_sql_query(
        "SELECT date, close FROM prices WHERE ticker = ? ORDER BY date",
        sample_db,
        params=(normalize_b3_ticker(ticker),),
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

    ticker = "PETR4"

    retorno.compute_returns(ticker, conn=sample_db)
    first_count = _count_returns(sample_db, ticker)

    # Run again
    retorno.compute_returns(ticker, conn=sample_db)
    second_count = _count_returns(sample_db, ticker)

    assert first_count == second_count


def test_compute_returns_range(sample_db):
    """compute_returns with start/end writes only rows within the requested range."""
    import src.retorno as retorno

    ticker = "PETR4"

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

    ticker = "PETR4"

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


def test_write_returns_preserves_created_at_when_upsert_not_supported(
    sample_db, monkeypatch
):
    """Force older SQLite runtime (no UPSERT) and ensure created_at is preserved.

    Uses `monkeypatch` to set `sqlite3.sqlite_version` to an old version so the
    transactional UPDATE->INSERT fallback path in `write_returns` is exercised.
    """
    import sqlite3

    import src.retorno as retorno

    # Force an older SQLite version to trigger fallback path
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.8.0")

    ticker = "PETR4"

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


def test_fallback_failure_logs_processed_count(monkeypatch):  # noqa: C901
    """Logger.exception is invoked with the number of rows processed.

    Instead of relying on the logging subsystem, we patch the logger to
    capture arguments directly.  This makes the test more deterministic and
    avoids fiddling with caplog levels.
    """
    from src.db import returns as returns_mod

    # force fallback branch and skip migrations (not needed here)
    monkeypatch.setattr(returns_mod, "_sqlite_version_tuple", lambda: (3, 8, 0))
    monkeypatch.setattr(returns_mod, "_migrate_returns_date_column", lambda conn: None)

    # spy on logger.exception
    called: list[tuple] = []

    def fake_exception(msg, *args, **kwargs):
        called.append((msg, args, kwargs))

    monkeypatch.setattr(returns_mod.logger, "exception", fake_exception)

    class FakeCursor:
        def __init__(self):
            self.rowcount = 0
            self.row_idx = 0

        def execute(self, sql, params=None):
            # only fail when updating second row
            # sourcery skip: no-conditionals-in-tests
            if sql.strip().startswith("UPDATE returns SET"):
                self.row_idx += 1
                if self.row_idx == 2:
                    raise RuntimeError("boom")
                self.rowcount = 0
            elif sql.strip().startswith("INSERT INTO returns"):
                self.rowcount = 0
            else:
                self.rowcount = 0

        def executemany(self, *args, **kwargs):
            raise RuntimeError("should not be used in fallback")

    class FakeConn:
        def __init__(self):
            self.cur = FakeCursor()

        def cursor(self):
            return self.cur

        def execute(self, sql, *args, **kwargs):
            return None

        def commit(self):
            pass

        def rollback(self):
            pass

    conn = FakeConn()
    df = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "date": ["2026-01-01", "2026-01-02"],
            "return_value": [1, 2],
        }
    )

    with pytest.raises(RuntimeError):
        returns_mod._write_returns_core(conn, df, return_type="daily")

    assert called, "logger.exception should have been called"
    msg, args, kwargs = called[0]
    assert "processed %d rows" in msg
    assert args and args[0] == 1


def _returns_table_exists(conn: sqlite3.Connection) -> bool:
    """Return True if the ``returns`` table exists in the database."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='returns'")
    return cur.fetchone() is not None


def _safe_count_returns(
    conn: sqlite3.Connection,
    ticker: str,
    return_type: str = "daily",
) -> int:
    """Count returns rows, returning 0 if the table does not exist."""
    if not _returns_table_exists(conn):
        return 0
    return _count_returns(conn, ticker, return_type)


def test_compute_returns_empty_and_single_price(sample_db):
    """Handle empty ticker (no prices) and single-price series gracefully."""
    import src.retorno as retorno

    # Empty ticker: should not raise and produce zero rows
    retorno.compute_returns("EMPTY_TICKER", conn=sample_db)
    assert _safe_count_returns(sample_db, "EMPTY_TICKER") == 0

    # Single price row: insert one price and expect zero returns
    cur = sample_db.cursor()
    cur.execute("PRAGMA table_info(prices)")
    existing_cols = [r[1] for r in cur.fetchall()]
    # Add optional columns present in the DB schema in table-order
    defaults = {"fetched_at": "2023-01-01T00:00:00", "raw_checksum": "0" * 64}
    present_cols = [c for c in existing_cols if c in defaults]
    cols = [
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
        *present_cols,
    ]
    vals = [
        "SINGLE",
        "2023-01-01",
        100.0,
        100.0,
        100.0,
        100.0,
        100,
        "fixture",
        *[defaults[c] for c in present_cols],
    ]
    placeholders = ",".join(["?" for _ in cols])
    sql = f"INSERT INTO prices ({','.join(cols)}) VALUES ({placeholders})"
    cur.execute(sql, tuple(vals))
    sample_db.commit()

    retorno.compute_returns("SINGLE", conn=sample_db)
    assert _safe_count_returns(sample_db, "SINGLE") == 0
