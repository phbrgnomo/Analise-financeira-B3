
import contextlib
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from src.paths import DATA_DIR

DEFAULT_DB_PATH = str(DATA_DIR / "data.db")
DEFAULT_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "docs", "schema.json"
)


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
        nullable = "" if c.get("nullable", True) else "NOT NULL"
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


def _build_row_tuple(vals: dict, schema_cols: list) -> tuple:
    return tuple(vals.get(col) for col in schema_cols)


def _sqlite_version_tuple() -> tuple[int, ...]:
    """Parse ``sqlite3.sqlite_version`` into a tuple of integers.

    Handles non-numeric suffixes like ``"3.44.0-alpha"`` by consuming only
    the leading digit characters of each version component. Returns a
    tuple of ints (e.g., ``(3, 44, 0)``) and stops parsing when a component
    has no leading digits.
    """
    parts: list[int] = []
    for part in sqlite3.sqlite_version.split("."):
        numeric = ""
        for ch in part:
            if ch.isdigit():
                numeric += ch
            else:
                break
        if not numeric:
            break
        parts.append(int(numeric))
    return tuple(parts)


def _get_upsert_sql(schema_cols: list) -> str:
    # Validate and quote column identifiers to avoid SQL injection via
    # malicious column names. Only allow a conservative identifier set.
    def _is_valid_identifier(name: str) -> bool:
        return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))

    def _quote_identifier(name: str) -> str:
        if not _is_valid_identifier(name):
            raise ValueError(f"Invalid column identifier: {name!r}")
        return f'"{name}"'

    quoted_cols = [_quote_identifier(c) for c in schema_cols]
    col_list_sql = ",".join(quoted_cols)
    placeholders = ",".join(["?" for _ in schema_cols])

    update_items = []
    for c in schema_cols:
        if c in ("ticker", "date"):
            continue
        qc = _quote_identifier(c)
        update_items.append(f"{qc}=excluded.{qc}")
    update_set = ",".join(update_items)

    # Parse sqlite3.sqlite_version defensively in case of non-numeric suffixes
    # e.g. "3.44.0-alpha" -> (3, 44, 0)
    sqlite_version = _sqlite_version_tuple()
    supports_upsert = sqlite_version >= (3, 24, 0)

    if supports_upsert:
        if update_set:
            return (
                "INSERT INTO prices ({cols}) VALUES ({vals}) "
                "ON CONFLICT(ticker,date) DO UPDATE SET {updates}"
            ).format(cols=col_list_sql, vals=placeholders, updates=update_set)
        # Nothing to update on conflict: DO NOTHING
        return (
            "INSERT INTO prices ({cols}) VALUES ({vals}) "
            "ON CONFLICT(ticker,date) DO NOTHING"
        ).format(cols=col_list_sql, vals=placeholders)

    # Fallback for older SQLite versions: replace entire row
    import warnings

    warnings.warn(
        (
            "SQLite version %s does not support UPSERT; falling back to "
            "INSERT OR REPLACE. Consider upgrading SQLite to >= 3.24.0 "
            "for safer ON CONFLICT semantics."
        ) % sqlite3.sqlite_version,
        stacklevel=2,
    )
    return ("INSERT OR REPLACE INTO prices ({cols}) VALUES ({vals})").format(
        cols=col_list_sql, vals=placeholders
    )


def _apply_pragmas(conn: sqlite3.Connection, db_path: Optional[str]) -> None:
    """Aplicar PRAGMAs em modo best-effort para DBs file-backed.

    Esta função encapsula a detecção de DB em memória e a execução dos
    PRAGMA `journal_mode=WAL` e `busy_timeout=30000`. Falhas são silenciadas
    para não quebrar testes que usam bancos em-memória ou plataformas
    sem suporte a WAL.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db_path = str(db_path)

    file_mode_memory = (
        db_path.startswith("file:")
        and ("mode=memory" in db_path or db_path.startswith("file::memory"))
    )
    is_memory = db_path == ":memory:" or file_mode_memory
    if is_memory:
        return

    cur = conn.cursor()
    # Apply PRAGMAs in best-effort mode for file-backed DBs. Each call is
    # individually suppressed to avoid breaking tests on platforms that do
    # not support WAL or when the underlying connection does not allow the
    # operation.
    with contextlib.suppress(Exception):
        cur.execute("PRAGMA journal_mode=WAL;")
    with contextlib.suppress(Exception):
        cur.execute("PRAGMA busy_timeout=30000;")
    with contextlib.suppress(Exception):
        _ = cur.fetchall()


def _row_tuple_from_series(
    idx, row, ticker, source, fetched_at, cols_map, schema_cols
) -> tuple:
    date_s = pd.to_datetime(idx).strftime("%Y-%m-%d")
    vals = {"ticker": ticker, "date": date_s, "source": source}

    src_col = cols_map.get("source")
    if src_col is not None and not pd.isna(row[src_col]):
        vals["source"] = str(row[src_col])

    for name in ["open", "high", "low", "close", "volume"]:
        col = cols_map.get(name)
        if col is not None and not pd.isna(row[col]):
            vals[name] = float(row[col]) if name != "volume" else int(row[col])
        else:
            vals[name] = None

    payload = (
        f"{ticker}|{date_s}|{vals.get('open')}|{vals.get('high')}|"
        f"{vals.get('low')}|{vals.get('close')}|{vals.get('volume')}|{source}"
    )

    vals["raw_checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    vals["fetched_at"] = fetched_at or datetime.now(timezone.utc).isoformat()

    return _build_row_tuple(vals, schema_cols)


def _connect(db_path: Optional[str]) -> sqlite3.Connection:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if dirname := os.path.dirname(os.path.abspath(db_path)):
        os.makedirs(dirname, exist_ok=True)
    # Use a reasonable Python-side timeout to reduce OperationalError race
    # conditions when multiple writers contend for the same file.
    conn = sqlite3.connect(db_path, timeout=30.0)

    # Apply PRAGMAs in best-effort mode for file-backed DBs. Skip applying
    # PRAGMAs for explicit in-memory connections to avoid breaking tests that
    # rely on :memory: semantics.
    # Apply PRAGMAs in best-effort mode for file-backed DBs.
    _apply_pragmas(conn, db_path)

    return conn


def init_db(db_path: Optional[str] = None, allow_external: bool = False) -> None:
    """Inicializa o banco (cria arquivo e schema) de forma idempotente.

    Parameters
    ----------
    db_path: Optional[str]
        Caminho para o arquivo .db. Quando None usa `DATA_DIR / 'data.db'`.
    allow_external: bool
        Parâmetro reservado para compatibilidade com scripts que validam
        caminhos externamente. Atualmente apenas influencia a passagem de
        `db_path` tal como recebido.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    # Use _connect to ensure parent directories are created safely and
    # to centralize connection logic (avoids os.makedirs('') when db_path
    # is a bare filename).
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        # Re-apply PRAGMAs after schema creation in best-effort mode.
        _apply_pragmas(conn, db_path)
    finally:
        conn.close()


def record_snapshot_metadata(
    metadata: dict,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> None:
    """Registra um resumo de snapshot/ingest na tabela `snapshots`.

    Armazena o JSON serializado no campo `payload` junto com `ticker` e
    `created_at` para consultas rápidas.
    """
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        _upsert_snapshot_metadata(conn, metadata)
    finally:
        if close_conn:
            conn.close()


def _upsert_snapshot_metadata(
    conn: sqlite3.Connection, metadata: dict[str, Any]
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                ticker TEXT,
                created_at TEXT,
                payload TEXT
            )
            """
    )
    job_id = (
        metadata.get("job_id")
        or metadata.get("id")
        or hashlib.sha256(
            json.dumps(metadata, sort_keys=True).encode("utf-8")
        ).hexdigest()
    )
    created_at = (
        metadata.get("created_at")
        or datetime.now(timezone.utc).isoformat()
    )
    ticker = metadata.get("ticker") or metadata.get("symbol") or None
    sql = (
        "INSERT OR REPLACE INTO snapshots(id, ticker, created_at, payload) "
        "VALUES (?, ?, ?, ?)"
    )
    cur.execute(
        sql,
        (
            job_id,
            ticker,
            created_at,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    conn.commit()


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

        # Derive insert column order from the actual DB table to avoid
        # mismatch between canonical JSON schema and the physical table.
        cur = conn.cursor()
        cur.execute("PRAGMA table_info('prices')")
        if table_info := cur.fetchall():
            # PRAGMA table_info returns rows where column name is at index 1
            schema_cols = [r[1] for r in table_info]
        else:
            # Fallback to canonical schema if table_info is empty for some reason
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
