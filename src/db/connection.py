"""Connection management: connect, init_db, PRAGMAs."""

import contextlib
import logging
import os
import sqlite3
from typing import Optional

from src.paths import DATA_DIR

DEFAULT_DB_PATH = str(DATA_DIR / "data.db")

logger = logging.getLogger(__name__)


def _apply_pragmas(conn: sqlite3.Connection, db_path: Optional[str]) -> None:
    """Aplicar PRAGMAs em modo best-effort para DBs file-backed.

    Esta função encapsula a detecção de DB em memória e a execução dos
    PRAGMA ``journal_mode=WAL`` e ``busy_timeout=30000``. Falhas são
    silenciadas para não quebrar testes que usam bancos em-memória ou
    plataformas sem suporte a WAL.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db_path = str(db_path)

    file_mode_memory = db_path.startswith("file:") and (
        "mode=memory" in db_path or db_path.startswith("file::memory")
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


def _connect(db_path: Optional[str]) -> sqlite3.Connection:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if dirname := os.path.dirname(os.path.abspath(db_path)):
        os.makedirs(dirname, exist_ok=True)
    # Use a reasonable Python-side timeout to reduce OperationalError race
    # conditions when multiple writers contend for the same file.
    conn = sqlite3.connect(db_path, timeout=30.0)

    # Apply PRAGMAs in best-effort mode for file-backed DBs.
    _apply_pragmas(conn, db_path)

    return conn


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Public connection factory.

    Mirrors the internal ``_connect`` behavior: creates parent directories
    when needed, applies PRAGMAs in best-effort mode and returns a
    ``sqlite3.Connection``. The returned connection can be used as a context
    manager (``with connect(...) as conn:``) or closed manually with
    ``conn.close()``.
    """
    return _connect(db_path)


def init_db(db_path: Optional[str] = None, allow_external: bool = False) -> None:
    """Inicializa o banco (cria arquivo e schema) de forma idempotente.

    Parameters
    ----------
    db_path : Optional[str]
        Caminho para o arquivo ``.db``. Quando ``None`` usa
        ``DATA_DIR / 'data.db'``.
    allow_external : bool
        Parâmetro reservado para compatibilidade com scripts que validam
        caminhos externamente. Atualmente apenas influencia a passagem de
        ``db_path`` tal como recebido.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    # Use _connect to ensure parent directories are created safely and
    # to centralize connection logic (avoids os.makedirs('') when db_path
    # is a bare filename).
    conn = _connect(db_path)
    try:
        from src.db.schema import _ensure_schema

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
        # Log successful initialization (best-effort; do not fail init on
        # logging)
        with contextlib.suppress(Exception):
            logger.info("database_initialized", extra={"db_path": db_path})
    finally:
        conn.close()
