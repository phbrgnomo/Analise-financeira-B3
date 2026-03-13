#!/usr/bin/env python3
"""Utility script to apply database migrations.

This script is used by CI workflows and can also be run locally when the
schema needs to be ensured before executing other commands. It reads the
optional ``DB_PATH`` environment variable (default ``dados/data.db``) and
invokes the :func:`src.db_migrator.apply_migrations` helper.

The script is intentionally simple so it can be executed via ``python`` or
made executable in a shell pipeline.
"""

import logging
import os
import sqlite3

from src.db_migrator import apply_migrations
from src.logging_config import configure_logging

# configure global logging before doing any work; tests may override level
configure_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    dbpath = os.getenv("DB_PATH", "dados/data.db")
    if db_dir := os.path.dirname(dbpath):
        os.makedirs(db_dir, exist_ok=True)

    # use context manager so connection is closed even if migrations fail
    with sqlite3.connect(dbpath) as conn:
        apply_migrations(conn)
    logger.info(f"migrations applied to {dbpath}")


if __name__ == "__main__":
    main()
