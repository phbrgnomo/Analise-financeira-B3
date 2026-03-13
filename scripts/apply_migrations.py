#!/usr/bin/env python3
"""Utility script to apply database migrations.

This script is used by CI workflows and can also be run locally when the
schema needs to be ensured before executing other commands. It reads the
optional ``DB_PATH`` environment variable (default ``dados/data.db``) and
invokes the :func:`src.db_migrator.apply_migrations` helper.

The script is intentionally simple so it can be executed via ``python`` or
made executable in a shell pipeline.
"""

import os
import sqlite3

from src.db_migrator import apply_migrations


def main() -> None:
    dbpath = os.getenv("DB_PATH", "dados/data.db")
    # ensure parent dir exists to avoid sqlite OperationalError on clean
    # checkouts (the same logic used by src.db.connection._connect).
    db_dir = os.path.dirname(dbpath)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(dbpath)
    apply_migrations(conn)
    conn.close()
    print(f"migrations applied to {dbpath}")


if __name__ == "__main__":
    main()
