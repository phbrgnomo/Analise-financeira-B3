"""
Camada de persistência SQLite para o pipeline de ingestão.

Expõe helpers para criação de schema (``_ensure_schema``), escrita idempotente
de preços (``write_prices``), leitura de preços históricos (``read_prices``),
registro de snapshots e metadados de ingestão.  O caminho padrão do banco é
``dados/data.db`` e pode ser sobrescrito via parâmetros ou variável de ambiente.
"""

import contextlib
import hashlib
import json
import logging
import os
import re
import sqlite3
import warnings
from typing import Any, Optional

import pandas as pd

from src.paths import DATA_DIR
from src.tickers import normalize_b3_ticker, ticker_variants
from src.time_utils import now_utc_iso

DEFAULT_DB_PATH = str(DATA_DIR / "data.db")
DEFAULT_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "docs", "schema.json"
)

logger = logging.getLogger(__name__)

# Track whether we've warned about missing UPSERT support to avoid noisy logs
# Ensure the UPSERT compatibility warning is emitted at most once per process.
# Use the warnings module "once" filter so we don't need manual synchronization.
warnings.filterwarnings(
    "once",
    message=(
        r"SQLite version .* does not support UPSERT; falling back to "
        r"INSERT OR REPLACE\. Consider upgrading SQLite to >= 3\.24\.0 "
        r"for safer ON CONFLICT semantics\."
    ),
    category=UserWarning,
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
        # use DATE type for columns of logical date
        "date": "DATE",
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
    _migrate_prices_date_column(conn)
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


def _normalize_db_ticker(ticker: str) -> str:
    candidate = ticker.strip().upper().removesuffix(".SA")
    try:
        return normalize_b3_ticker(candidate)
    except ValueError:
        return candidate


def _migrate_prices_date_column(conn: sqlite3.Connection) -> None:
    """Garante afinidade DATE para `prices.date` de forma idempotente."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info('prices')")
    info = cur.fetchall()
    if not info:
        return

    existing_types = {row[1]: (row[2] or "").upper() for row in info}
    if existing_types.get("date") == "DATE":
        return

    required_cols = {"ticker", "date", "source", "raw_checksum", "fetched_at"}
    if not required_cols.issubset(set(existing_types.keys())):
        return

    schema = _load_canonical_schema()
    schema_cols = [c["name"] for c in schema.get("columns", [])]
    col_defs = []
    for col in schema.get("columns", []):
        name = col["name"]
        typ = _sql_type(col.get("type", "string"))
        nullable = "" if col.get("nullable", True) else "NOT NULL"
        col_defs.append(f"{name} {typ} {nullable}".strip())

    create_sql = (
        "CREATE TABLE prices_tmp_date_migration ("
        + ", ".join(col_defs)
        + ", PRIMARY KEY (ticker, date))"
    )

    common_cols = [c for c in schema_cols if c in existing_types]
    if not common_cols:
        return
    cols_csv = ", ".join(common_cols)

    cur.execute(create_sql)
    cur.execute(
        f"INSERT OR REPLACE INTO prices_tmp_date_migration ({cols_csv}) "
        f"SELECT {cols_csv} FROM prices"
    )
    cur.execute("DROP TABLE prices")
    cur.execute("ALTER TABLE prices_tmp_date_migration RENAME TO prices")
    conn.commit()


def _migrate_returns_date_column(conn: sqlite3.Connection) -> None:
    """Garante afinidade DATE para `returns.date` de forma idempotente."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info('returns')")
    info = cur.fetchall()
    if not info:
        return

    existing_types = {row[1]: (row[2] or "").upper() for row in info}
    if existing_types.get("date") == "DATE":
        return

    cur.execute(
        "CREATE TABLE returns_tmp_date_migration ("
        "ticker TEXT, "
        "date DATE, "
        "return_value REAL, "
        "return_type TEXT, "
        "created_at TEXT, "
        "UNIQUE(ticker, date, return_type)"
        ")"
    )
    cur.execute(
        "INSERT OR REPLACE INTO returns_tmp_date_migration "
        "(ticker, date, return_value, return_type, created_at) "
        "SELECT ticker, date, return_value, return_type, created_at FROM returns"
    )
    cur.execute("DROP TABLE returns")
    cur.execute("ALTER TABLE returns_tmp_date_migration RENAME TO returns")
    conn.commit()


def _build_row_tuple(vals: dict, schema_cols: list) -> tuple:
    return tuple(vals.get(col) for col in schema_cols)


# Identifier helpers lifted to module level so read and write paths share the
# same validation and quoting rules. Keeps SQL construction robust against
# reserved words or unexpected characters in schema-derived column names.
def _is_valid_identifier(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))


def _quote_identifier(name: str) -> str:
    if not _is_valid_identifier(name):
        raise ValueError(f"Invalid column identifier: {name!r}")
    return f'"{name}"'


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
    # Quote column identifiers using module-level helpers to ensure both
    # read and write paths use identical validation logic.
    quoted_cols = [_quote_identifier(c) for c in schema_cols]
    col_list_sql = ",".join(quoted_cols)
    placeholders = ",".join(["?" for _ in schema_cols])

    update_items = []
    for c in schema_cols:
        if c in ("ticker", "date"):
            continue
        qc = _quote_identifier(c)
        update_items.append(f"{qc}=excluded.{qc}")
    # Parse sqlite3.sqlite_version defensively in case of non-numeric suffixes
    # e.g. "3.44.0-alpha" -> (3, 44, 0)
    sqlite_version = _sqlite_version_tuple()
    supports_upsert = sqlite_version >= (3, 24, 0)

    if supports_upsert:
        if update_set := ",".join(update_items):
            return (
                "INSERT INTO prices ({cols}) VALUES ({vals}) "
                "ON CONFLICT(ticker,date) DO UPDATE SET {updates}"
            ).format(cols=col_list_sql, vals=placeholders, updates=update_set)
        # Nothing to update on conflict: DO NOTHING
        return (
            "INSERT INTO prices ({cols}) VALUES ({vals}) "
            "ON CONFLICT(ticker,date) DO NOTHING"
        ).format(cols=col_list_sql, vals=placeholders)

    # Ensure the assumed conflict target exists in the schema
    if "ticker" not in schema_cols or "date" not in schema_cols:
        raise ValueError(
            "Schema does not contain required 'ticker' and 'date' columns for upsert; "
            "check docs/schema.json and _ensure_schema()"
        )

    # Fallback for older SQLite versions: replace entire row
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
    normalized_ticker = _normalize_db_ticker(ticker)
    vals = {
        "ticker": normalized_ticker,
        "date": date_s,
        "source": source,
    }

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
        f"{normalized_ticker}|{date_s}|{vals.get('open')}|{vals.get('high')}|"
        f"{vals.get('low')}|{vals.get('close')}|{vals.get('volume')}|{source}"
    )

    vals["raw_checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    vals["fetched_at"] = fetched_at or now_utc_iso()

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


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Public connection factory.

    Mirrors the internal `_connect` behavior: creates parent directories
    when needed, applies PRAGMAs in best-effort mode and returns a
    sqlite3.Connection. The returned connection can be used as a context
    manager (``with connect(...) as conn:``) or closed manually with
    ``conn.close()``.
    """
    return _connect(db_path)


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
        # Apply SQL migrations if present
        try:
            from src.db_migrator import apply_migrations

            apply_migrations(conn)
        except Exception:
            # Migration failures should bubble up in production; for init we
            # log and re-raise to avoid silent schema drift.
            conn.close()
            raise
        # Log successful initialization (best-effort; do not fail init on logging)
        with contextlib.suppress(Exception):
            logger.info("database_initialized", extra={"db_path": db_path})
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
    created_at = metadata.get("created_at") or now_utc_iso()
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
    # normalize ticker to base B3 form (strip .SA) for storage consistency
    try:
        from src.tickers import normalize_b3_ticker

        ticker = normalize_b3_ticker(ticker)
    except Exception:
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
    """Read price rows for `ticker` and return a pandas DataFrame indexed by date.

    Parameters
    ----------
    ticker:
        Ticker identifier (e.g. "PETR4.SA").
    start, end:
        Optional date bounds (``YYYY-MM-DD``) to filter rows.
    conn:
        Optional ``sqlite3.Connection`` instance to use. When provided, the
        function will use this connection and will not open/close a new one.
    db_path:
        Optional path or URI to an SQLite database file. When ``conn`` is None,
        the function will open a connection to ``db_path`` (or the default
        DB path) and close it before returning.

    Returns
    -------
    pandas.DataFrame
        DataFrame indexed by date with columns from the canonical schema. If
        no rows are found an empty DataFrame is returned.
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
        sql = f"SELECT {', '.join(quoted_select)} FROM prices WHERE ticker = ?"
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
        cur.execute(
            "SELECT DISTINCT ticker FROM prices ORDER BY ticker"
        )
        return [row[0] for row in cur.fetchall() if row and row[0]]
    finally:
        if close_conn:
            conn.close()


def resolve_existing_ticker(
    ticker: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> Optional[str]:
    """Resolve ticker existente em ``prices`` aceitando base e variante `.SA`.

    Retorna o ticker persistido quando houver correspondência; caso contrário,
    retorna ``None``.
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
            if base in existing:
                return base
            if provider in existing:
                return provider
        return existing[0]
    finally:
        if close_conn:
            conn.close()


def write_returns(
    df: pd.DataFrame,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
    return_type: str = "daily",
):
    # ensure ticker values inside df are canonical (strip .SA)
    if "ticker" in df.columns:
        df = df.copy()
        df["ticker"] = df["ticker"].astype(str).str.replace(".SA", "", regex=False)
    """Persist returns DataFrame into `returns` table using upsert semantics.

    Expects DataFrame columns: `ticker`, `date` (datetime or string), `return_value`,
    optionally `return_type` and `created_at`. The function is idempotent and
    will create the `returns` table if missing.
    """
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
    # Quote identifiers to avoid conflicts with reserved words (e.g. RETURN)
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
    # Prefer modern UPSERT syntax when supported by the SQLite runtime to
    # preserve finer-grained update semantics (e.g., avoid overwriting
    # created_at unless necessary). Fallback to INSERT OR REPLACE for
    # older SQLite versions.
    sqlite_version = _sqlite_version_tuple()
    supports_upsert = sqlite_version >= (3, 24, 0)

    # Build parameterized INSERT/UPSERT using quoted identifiers to ensure
    # reserved keywords like `return` are handled safely and consistently.
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
        # support the UPSERT syntax. Instead of using `INSERT OR REPLACE` (which
        # may overwrite existing rows and lose metadata like `created_at`), we
        # perform an UPDATE first and INSERT only when no existing row was
        # updated. This preserves `created_at` and avoids destructive replaces.
        update_sql = (
            f"UPDATE returns SET {qr} = ? "
            f"WHERE {qt} = ? AND {qd} = ? AND {qrt} = ?"
        )
        insert_sql = f"INSERT INTO returns ({cols_sql}) VALUES (?,?,?,?,?)"

        logger = logging.getLogger(__name__)
        try:
            conn.execute("BEGIN")
            for row in rows:
                # row order: ticker, date, return, return_type, created_at
                ticker_val, date_val, return_val, rtype_val, created_at_val = row
                cur.execute(update_sql, (return_val, ticker_val, date_val, rtype_val))
                if cur.rowcount == 0:
                    cur.execute(insert_sql, row)
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Failed transactional upsert fallback for returns")
            raise
