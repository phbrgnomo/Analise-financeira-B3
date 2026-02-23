
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

import pandas as pd

DEFAULT_DB_PATH = os.path.join(os.getcwd(), "dados", "data.db")
DEFAULT_SCHEMA_PATH = os.path.join(os.getcwd(), "docs", "schema.json")


def _load_canonical_schema(schema_path: Optional[str] = None) -> dict:
    path = schema_path or DEFAULT_SCHEMA_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to minimal in-code schema to avoid hard failure in tests
        return {
            "schema_version": 1,
            "columns": [
                {"name": "ticker", "type": "string", "nullable": False},
                {"name": "date", "type": "date", "nullable": False},
                {"name": "open", "type": "float", "nullable": True},
                {"name": "high", "type": "float", "nullable": True},
                {"name": "low", "type": "float", "nullable": True},
                {"name": "close", "type": "float", "nullable": True},
                {"name": "volume", "type": "int", "nullable": True},
                {"name": "source", "type": "string", "nullable": False},
                {"name": "fetched_at", "type": "datetime", "nullable": False},
                {"name": "raw_checksum", "type": "string", "nullable": False},
            ],
        }


def _sql_type(col_type: str) -> str:
    mapping = {
        "string": "TEXT",
        "date": "TEXT",
        "datetime": "TEXT",
        "float": "REAL",
        "int": "INTEGER",
    }
    return mapping.get(col_type, "TEXT")


def _ensure_schema(conn: sqlite3.Connection, schema_path: Optional[str] = None) -> None:
    schema = _load_canonical_schema(schema_path)
    cols = schema.get("columns", [])

    col_sql_parts = []
    for c in cols:
        name = c["name"]
        typ = _sql_type(c.get("type", "string"))
        nullable = "NOT NULL" if not c.get("nullable", True) else ""
        col_sql_parts.append(f"{name} {typ} {nullable}".strip())

    # Ensure PK on (ticker,date) if those columns exist
    names = [c["name"] for c in cols]
    pk = "(ticker, date)" if "ticker" in names and "date" in names else ""
    pk_sql = f", PRIMARY KEY {pk}" if pk else ""

    create_prices = (
        "CREATE TABLE IF NOT EXISTS prices (" +
        ", ".join(col_sql_parts) + pk_sql + ")"
    )

    cur = conn.cursor()
    cur.execute(create_prices)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    # Persist schema_version from canonical schema
    sv = str(schema.get("schema_version", 1))
    cur.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
        ("schema_version", sv),
    )
    conn.commit()


def _connect(db_path: Optional[str]) -> sqlite3.Connection:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return sqlite3.connect(db_path)


def write_prices(
    df: pd.DataFrame,
    ticker: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
    source: str = "provider",
    fetched_at: Optional[str] = None,
):
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
            raise ValueError("DataFrame must have a DatetimeIndex or a 'date' column")

        cols_map = {c.lower(): c for c in df.columns}

        # Load canonical schema to determine columns and insert order
        schema = _load_canonical_schema()
        schema_cols = [c["name"] for c in schema.get("columns", [])]

        # Ensure computed columns exist
        if "raw_checksum" not in schema_cols:
            schema_cols.append("raw_checksum")
        if "fetched_at" not in schema_cols:
            schema_cols.append("fetched_at")

        rows = []
        for idx, row in df.iterrows():
            date_s = pd.to_datetime(idx).strftime("%Y-%m-%d")
            vals = {
                "ticker": ticker,
                "date": date_s,
                "source": source,
            }

            # Map provider columns (case-insensitive)
            for name in ["open", "high", "low", "close", "volume"]:
                col = cols_map.get(name)
                if col is not None and not pd.isna(row[col]):
                    vals[name] = float(row[col]) if name != "volume" else int(row[col])
                else:
                    vals[name] = None

            # Build a stable payload string for checksum
            payload = (
                f"{ticker}|{date_s}|{vals.get('open')}|{vals.get('high')}|"
                f"{vals.get('low')}|{vals.get('close')}|{vals.get('volume')}|{source}"
            )
            vals["raw_checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            vals["fetched_at"] = fetched_at or datetime.utcnow().isoformat()

            # Build row tuple in schema order
            row_tuple = tuple(vals.get(col) for col in schema_cols)
            rows.append(row_tuple)

        col_list_sql = ",".join(schema_cols)
        placeholders = ",".join(["?" for _ in schema_cols])
        update_items = [
            f"{c}=excluded.{c}" for c in schema_cols if c not in ("ticker", "date")
        ]
        update_set = ",".join(update_items)

        sql = (
            "INSERT INTO prices ({} ) VALUES ({} ) "
            "ON CONFLICT(ticker,date) DO UPDATE SET {}"
        ).format(col_list_sql, placeholders, update_set)

        cur = conn.cursor()
        cur.executemany(sql, rows)
        conn.commit()
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
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        cur = conn.cursor()
        params = [ticker]
        schema = _load_canonical_schema()
        schema_cols = [c["name"] for c in schema.get("columns", [])]
        # ensure date is selected first
        select_cols = [c for c in schema_cols if c != "date"]
        select_cols = ["date"] + select_cols
        sql = f"SELECT {', '.join(select_cols)} FROM prices WHERE ticker = ?"
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
    finally:
        if close_conn:
            conn.close()
