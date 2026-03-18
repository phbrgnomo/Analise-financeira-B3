"""Schema management: loading, type mapping, DDL generation and upsert SQL."""

import json
import logging
import sqlite3
import warnings
from typing import Optional

from src.db._helpers import (
    _quote_identifier,
    _sqlite_version_tuple,
)
from src.paths import project_root

DEFAULT_SCHEMA_PATH = str(project_root() / "docs" / "schema.json")

logger = logging.getLogger(__name__)


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


def _ensure_schema(
    conn: sqlite3.Connection, schema_path: Optional[str] = None
) -> None:
    """
    Ensure the database schema exists and is up to date.

    Creates the prices and metadata tables if they don't exist, runs
    necessary migrations, and persists the schema version.

    Args:
        conn: SQLite database connection.
        schema_path: Optional path to schema JSON file; defaults to
            docs/schema.json.
    """
    schema = _load_canonical_schema(schema_path)
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
        "CREATE TABLE IF NOT EXISTS prices ("
        + ", ".join(col_sql_parts) + pk_sql + ")"
    )

    cur = conn.cursor()
    cur.execute(create_prices)
    # only trigger the potentially expensive date-column migration if the
    # database hasn't already been bumped to user_version >= 1.  the
    # migration helper repeats this same check internally, but avoiding the
    # call entirely saves a PRAGMA/table_info round-trip on every
    # ``_ensure_schema`` invocation (see sourcery warning on line 140).
    cur.execute("PRAGMA user_version")
    version = cur.fetchone()[0] or 0
    if version < 1:
        # Deferred import to avoid circular dependency between schema and
        # migrations modules.
        from src.db.migrations import _migrate_prices_date_column

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
            "Schema does not contain required 'ticker' and 'date' columns "
            "for upsert; check docs/schema.json and _ensure_schema()"
        )

    # Fallback for older SQLite versions: replace entire row
    warnings.warn(
        (
            "SQLite version %s does not support UPSERT; falling back to "
            "INSERT OR REPLACE. Consider upgrading SQLite to >= 3.24.0 "
            "for safer ON CONFLICT semantics."
        )
        % sqlite3.sqlite_version,
        stacklevel=2,
    )
    return ("INSERT OR REPLACE INTO prices ({cols}) VALUES ({vals})").format(
        cols=col_list_sql, vals=placeholders
    )
