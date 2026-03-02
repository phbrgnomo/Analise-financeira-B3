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
# ``connect`` and ``init_db`` are the primary entrypoints for consumers.  the
# internal ``_connect`` alias and pragmas helper are retained in the
# :mod:`src.db.connection` module for callers that really need them but are not
# exported here.
from src.db.connection import (  # noqa: F401
    DEFAULT_DB_PATH,
    connect,
    init_db,
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
