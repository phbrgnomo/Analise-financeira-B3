"""Price CRUD operations: write, read, list, resolve."""

import logging
import sqlite3
from typing import Optional, Sequence

import pandas as pd

from src.db._helpers import (
    _quote_identifier,
    _row_tuple_from_series,
)
from src.db.connection import _connect
from src.db.schema import _ensure_schema, _get_upsert_sql, _load_canonical_schema
from src.tickers import normalize_b3_ticker, ticker_variants

logger = logging.getLogger(__name__)


def write_prices(  # noqa: C901
    df: pd.DataFrame,
    ticker: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
    source: str = "provider",
    fetched_at: Optional[str] = None,
):
    """Persist price DataFrame into ``prices`` table with upsert semantics."""
    # normalize ticker to base B3 form (strip .SA) for storage consistency
    try:
        ticker = normalize_b3_ticker(ticker)
    except Exception:
        # fallback remains the old-style normalization for invalid input
        ticker = ticker.strip().upper().removesuffix(".SA")
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        _ensure_schema(conn)

        df = df.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            df = df.set_index("date")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(
                "DataFrame must have a DatetimeIndex or a 'date' column"
            )

        cols_map = {c.lower(): c for c in df.columns}

        # Derive insert column order from the actual DB table to avoid
        # mismatch between canonical JSON schema and the physical table.
        cur = conn.cursor()
        cur.execute("PRAGMA table_info('prices')")
        if table_info := cur.fetchall():
            # PRAGMA table_info returns rows where column name is at index 1
            schema_cols = [r[1] for r in table_info]
        else:
            # Fallback to canonical schema if table_info is empty
            schema = _load_canonical_schema()
            schema_cols = [c["name"] for c in schema.get("columns", [])]
            # Ensure computed columns exist in the fallback
            if "raw_checksum" not in schema_cols:
                schema_cols.append("raw_checksum")
            if "fetched_at" not in schema_cols:
                schema_cols.append("fetched_at")

        rows = []
        rows.extend(
            _row_tuple_from_series(
                idx, row, ticker, source, fetched_at, cols_map, schema_cols
            )
            for idx, row in df.iterrows()
        )
        sql = _get_upsert_sql(schema_cols)

        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
    except Exception:  # rollback on failure to avoid partial commits
        try:
            conn.rollback()
        except Exception:  # pragma: no cover - best effort
            logger.exception("rollback failed after write_prices error")
        # re-raise so callers can respond to the original error
        raise
    finally:
        if close_conn:
            conn.close()


def read_prices(
    ticker: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> pd.DataFrame:
    """Read price rows for ``ticker`` and return a DataFrame indexed by date.

    Parameters
    ----------
    ticker :
        Ticker identifier (e.g. ``"PETR4.SA"``).
    start, end :
        Optional date bounds (``YYYY-MM-DD``) to filter rows.
    conn :
        Optional ``sqlite3.Connection`` instance to use.
    db_path :
        Optional path or URI to an SQLite database file.

    Returns
    -------
    pandas.DataFrame
        DataFrame indexed by date with columns from the canonical schema.
        If no rows are found an empty DataFrame is returned.
    """
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        return _read_prices_core(conn, ticker, start, end)
    finally:
        if close_conn:
            conn.close()


def _read_prices_core(
    conn: sqlite3.Connection,
    ticker: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    cur = conn.cursor()
    try:
        base, provider = ticker_variants(ticker)
        candidates = (base, provider)
    except ValueError:
        candidates = (ticker,)

    params: list[str] = list(candidates)
    schema = _load_canonical_schema()
    schema_cols = [c["name"] for c in schema.get("columns", [])]
    # ensure date is selected first
    select_cols = [c for c in schema_cols if c != "date"]
    select_cols = ["date"] + select_cols
    # Validate and quote column identifiers for the SELECT clause to avoid
    # SQL injection or malformed queries when schema contains unexpected
    # names. Column names used as DataFrame columns remain unquoted.
    quoted_select = [_quote_identifier(c) for c in select_cols]
    if len(candidates) == 2:
        sql = (
            f"SELECT {', '.join(quoted_select)} FROM prices "
            "WHERE ticker IN (?, ?)"
        )
    else:
        sql = (
            f"SELECT {', '.join(quoted_select)} FROM prices WHERE ticker = ?"
        )
    if start and end:
        sql += " AND date BETWEEN ? AND ?"
        params.extend([start, end])
    elif start:
        sql += " AND date >= ?"
        params.append(start)
    elif end:
        sql += " AND date <= ?"
        params.append(end)

    sql += " ORDER BY date"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = select_cols
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def list_price_tickers(
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> list[str]:
    """Lista tickers existentes na tabela ``prices`` em ordem alfabética."""
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT ticker FROM prices ORDER BY ticker")
        return [row[0] for row in cur.fetchall() if row and row[0]]
    finally:
        if close_conn:
            conn.close()


def resolve_existing_ticker(
    ticker: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> Optional[str]:
    """Resolve ticker existente em ``prices`` aceitando base e variante ``.SA``.

    Retorna o ticker persistido quando houver correspondência; caso
    contrário, retorna ``None``.
    """
    try:
        base, provider = ticker_variants(ticker)
        candidates = (base, provider)
    except ValueError:
        candidates = (ticker,)

    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        return _query_existing_tickers(conn, candidates)
    finally:
        if close_conn:
            conn.close()


def _query_existing_tickers(
    conn: sqlite3.Connection, candidates: Sequence[str]
):
    """Consulta quais tickers dos candidatos já existem na tabela prices."""
    cur = conn.cursor()
    if len(candidates) == 2:
        cur.execute(
            "SELECT DISTINCT ticker FROM prices WHERE ticker IN (?, ?)",
            candidates,
        )
    else:
        cur.execute(
            "SELECT DISTINCT ticker FROM prices WHERE ticker = ?",
            candidates,
        )
    existing = [row[0] for row in cur.fetchall() if row and row[0]]
    if not existing:
        return None
    if len(candidates) == 2:
        # use candidates tuple rather than bare variables to avoid
        # "possibly unbound" warnings when ticker_variants raised
        if candidates[0] in existing:
            return candidates[0]
        if candidates[1] in existing:
            return candidates[1]
    return existing[0]
