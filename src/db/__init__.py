"""Camada de persistência SQLite para o pipeline de ingestão.

Este pacote expõe helpers para criação de schema, escrita idempotente de
preços, leitura de preços históricos, registro de snapshots e metadados de
ingestão.  O caminho padrão do banco é ``dados/data.db`` e pode ser
sobrescrito via parâmetros ou variável de ambiente.

Todos os símbolos públicos são re-exportados aqui para manter
compatibilidade retroativa com ``import src.db as _db`` e
``from src.db import ...``.
"""

# -- connection ---------------------------------------------------------
# -- schema / helpers (semi-public, used by tests) ----------------------
from src.db._helpers import (
    _build_row_tuple,
    _is_valid_identifier,
    _normalize_db_ticker,
    _quote_identifier,
    _row_tuple_from_series,
    _sqlite_version_tuple,
)

# -- internal aliases for backward compatibility (some callers use
#    ``src.db._connect``) ------------------------------------------------
from src.db.connection import (  # noqa: F401
    DEFAULT_DB_PATH,
    _apply_pragmas,
    _connect,
    connect,
    init_db,
)

# -- migrations ---------------------------------------------------------
from src.db.migrations import (
    _migrate_prices_date_column,
    _migrate_returns_date_column,
    _recreate_returns_table_with_date_type,
)

# -- prices -------------------------------------------------------------
from src.db.prices import (
    list_price_tickers,
    read_prices,
    resolve_existing_ticker,
    write_prices,
)

# -- returns ------------------------------------------------------------
from src.db.returns import write_returns
from src.db.schema import (
    _ensure_schema,
    _get_upsert_sql,
    _load_canonical_schema,
    _sql_type,
)

# -- snapshots ----------------------------------------------------------
from src.db.snapshots import (
    get_last_snapshot_payload,
    record_snapshot_metadata,
)

__all__ = [
    # connection
    "DEFAULT_DB_PATH",
    "connect",
    "init_db",
    # schema helpers
    "_build_row_tuple",
    "_ensure_schema",
    "_get_upsert_sql",
    "_is_valid_identifier",
    "_load_canonical_schema",
    "_normalize_db_ticker",
    "_quote_identifier",
    "_row_tuple_from_series",
    "_sql_type",
    "_sqlite_version_tuple",
    # migrations
    "_migrate_prices_date_column",
    "_migrate_returns_date_column",
    "_recreate_returns_table_with_date_type",
    # prices
    "list_price_tickers",
    "read_prices",
    "resolve_existing_ticker",
    "write_prices",
    # returns
    "write_returns",
    # snapshots
    "get_last_snapshot_payload",
    "record_snapshot_metadata",
]
