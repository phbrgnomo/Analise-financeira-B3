"""Returns persistence: write_returns and helpers."""

import logging
import sqlite3
from typing import Optional

import pandas as pd

from src.db._helpers import (
    _normalize_db_ticker,
    _quote_identifier,
    _sqlite_version_tuple,
)
from src.db.connection import _connect
from src.db.migrations import _migrate_returns_date_column
from src.time_utils import now_utc_iso

logger = logging.getLogger(__name__)


def write_returns(
    df: pd.DataFrame,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
    return_type: str = "daily",
):
    """Persist returns DataFrame into ``returns`` table using upsert semantics.

    Expects DataFrame columns: ``ticker``, ``date`` (datetime or string),
    ``return_value``, optionally ``return_type`` and ``created_at``.  The
    function is idempotent and will create the ``returns`` table if missing.
    """
    # ensure ticker values inside df are canonical (strip .SA)
    if "ticker" in df.columns:
        df = df.copy()
        df["ticker"] = df["ticker"].astype(str).str.replace(".SA", "", regex=False)
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        _write_returns_core(conn, df, return_type)
    finally:
        if close_conn:
            conn.close()


def _write_returns_core(conn, df, return_type):
    cur = conn.cursor()
    # Ensure returns table exists with unique constraint for upsert
    # Quote identifiers to avoid conflicts with reserved words
    qt = _quote_identifier("ticker")
    qd = _quote_identifier("date")
    qr = _quote_identifier("return_value")
    qrt = _quote_identifier("return_type")
    qc = _quote_identifier("created_at")
    qtab = _quote_identifier("returns")

    cur.execute(
        (
            "CREATE TABLE IF NOT EXISTS returns ("
            f"{qt} TEXT, {qd} DATE, {qr} REAL, {qrt} TEXT, {qc} TEXT, "
            f"UNIQUE({qt}, {qd}, {qrt})"
            ")"
        )
    )
    _migrate_returns_date_column(conn)

    # Normalize DataFrame
    df2 = df.copy()
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"]).dt.tz_localize(None)
    else:
        raise ValueError("DataFrame must contain 'date' column")

    if "return_type" not in df2.columns:
        df2["return_type"] = return_type
    if "created_at" not in df2.columns:
        df2["created_at"] = now_utc_iso()

    rows = [
        (
            _normalize_db_ticker(str(r["ticker"])),
            r["date"].strftime("%Y-%m-%d"),
            float(r["return_value"]),
            r["return_type"],
            r["created_at"],
        )
        for _, r in df2.iterrows()
    ]
    # Prefer modern UPSERT syntax when supported by the SQLite runtime
    sqlite_version = _sqlite_version_tuple()
    supports_upsert = sqlite_version >= (3, 24, 0)

    # Build parameterized INSERT/UPSERT using quoted identifiers
    cols_sql = f"{qt}, {qd}, {qr}, {qrt}, {qc}"
    conflict_sql = f"{qt},{qd},{qrt}"

    if supports_upsert:
        sql = (
            f"INSERT INTO returns ({cols_sql}) VALUES (?,?,?,?,?) "
            f"ON CONFLICT({conflict_sql}) DO UPDATE SET "
            f"{qr}=excluded.{qr}, "
            f"{qc}=COALESCE({qtab}.{qc}, excluded.{qc})"
        )
        cur.executemany(sql, rows)
        conn.commit()
    else:
        # Safe transactional fallback for older SQLite runtimes that do not
        # support the UPSERT syntax. Performs UPDATE first and INSERT only
        # when no existing row was updated. Preserves ``created_at``.
        update_sql = (
            f"UPDATE returns SET {qr} = ? WHERE {qt} = ? AND {qd} = ? AND {qrt} = ?"
        )
        insert_sql = f"INSERT INTO returns ({cols_sql}) VALUES (?,?,?,?,?)"

        # track how many rows have been handled in case an error
        # occurs before the loop (e.g. BEGIN failure); initialize here
        processed = 0
        try:
            conn.execute("BEGIN")
            for row in rows:
                (
                    ticker_val,
                    date_val,
                    return_val,
                    rtype_val,
                    created_at_val,
                ) = row
                cur.execute(
                    update_sql,
                    (return_val, ticker_val, date_val, rtype_val),
                )
                if cur.rowcount == 0:
                    cur.execute(insert_sql, row)
                processed += 1
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception(
                "Failed transactional upsert fallback for returns; processed %d rows",
                processed,
            )
            raise
