import os
import sqlite3
from typing import Optional


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
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


def _applied_migrations(conn: sqlite3.Connection) -> set:
    cur = conn.cursor()
    cur.execute("SELECT id FROM schema_migrations")
    return set(r[0] for r in cur.fetchall())


def apply_migrations(conn: sqlite3.Connection, migrations_dir: Optional[str] = None) -> None:
    """Apply SQL migrations found in `migrations_dir` in alphanumeric order.

    Records applied migration ids in `schema_migrations` table to avoid re-applying.
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
            continue
        path = os.path.join(migrations_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            sql = f.read()
        try:
            cur.executescript(sql)
            cur.execute("INSERT INTO schema_migrations(id, applied_at) VALUES (?, datetime('now'))", (fname,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
