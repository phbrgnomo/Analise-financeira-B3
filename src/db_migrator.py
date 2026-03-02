"""Utilitário de migração de schema SQLite para o banco de dados do projeto.

Gerencia uma tabela de controle ``schema_migrations`` e aplica scripts SQL
encontrados em ``migrations/`` de forma idempotente — cada arquivo é aplicado
apenas uma vez. Use :func:`apply_migrations` para executar as migrações
pendentes numa conexão existente. A tabela ``schema_migrations`` registra o
identificador e o momento de aplicação de cada script para evitar reaplicação.
"""

import logging
import os
import sqlite3
from typing import Optional, Set

# sqlparse provides a safe way to split SQL scripts into individual
# statements without breaking on semicolons contained within literals or
# comments. Use it if available; otherwise fall back to naive splitting.
try:
    import sqlparse
except ImportError:  # pragma: no cover - dependency optional
    sqlparse = None

logger = logging.getLogger(__name__)


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Garante que a tabela schema_migrations exista na conexão SQLite fornecida."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT
        )
        """
    )
    conn.commit()


def _applied_migrations(conn: sqlite3.Connection) -> Set[str]:
    """Consulta a tabela schema_migrations e retorna um conjunto de
    IDs de migrações aplicadas."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM schema_migrations")
    return {r[0] for r in cur.fetchall()}


def apply_migrations(
    conn: sqlite3.Connection, migrations_dir: Optional[str] = None
) -> None:
    """Aplica migrações SQL encontradas em `migrations_dir` em ordem alfanumérica.

    Registra os IDs das migrações aplicadas na tabela `schema_migrations` para
    evitar reaplicação.
    """
    if migrations_dir is None:
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        migrations_dir = os.path.abspath(migrations_dir)

    if not os.path.isdir(migrations_dir):
        return

    _ensure_migrations_table(conn)
    applied = _applied_migrations(conn)

    files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
    cur = conn.cursor()
    for fname in files:
        if fname in applied:
            logger.debug("migration already applied, skipping: %s", fname)
            continue
        path = os.path.join(migrations_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            sql = f.read()
        try:
            # Run each migration file in its own transaction: execute all
            # statements from the file, record the filename in
            # schema_migrations, then commit.  This keeps failures scoped to a
            # single migration rather than bundling everything.
            # split the migration text into individual statements
            if sqlparse:
                statements = [s.strip() for s in sqlparse.split(sql) if s.strip()]
            else:
                # fallback: naive split on semicolon.  This may break when
                # semicolons appear in strings/comments, so installing
                # `sqlparse` is strongly recommended for real migrations.
                statements = [s.strip() for s in sql.split(";") if s.strip()]
            for stmt in statements:
                cur.execute(stmt)

            insert_sql = (
                "INSERT INTO schema_migrations(id, applied_at) "
                "VALUES (?, datetime('now'))"
            )
            cur.execute(insert_sql, (fname,))
            conn.commit()
            logger.info("migration applied successfully: %s", fname)
        except Exception as e:
            # rollback before propagating; provide context for easier debugging
            conn.rollback()
            logger.error("migration failed: %s — %s", fname, e)
            raise RuntimeError(f"migration failed ({fname})") from e
