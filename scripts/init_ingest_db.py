#!/usr/bin/env python3
"""Script de inicialização do banco de dados de ingest (dados/data.db).

Cria o arquivo .db e a tabela ingest_logs sem alterar o restante do pipeline.
Uso: python scripts/init_ingest_db.py --db dados/data.db
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from src.paths import DATA_DIR


def init_db(db_path: Path | str = DATA_DIR / "data.db") -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ingest_logs (
                job_id TEXT PRIMARY KEY,
                source TEXT,
                fetched_at TEXT,
                raw_checksum TEXT,
                rows INTEGER,
                filepath TEXT,
                status TEXT,
                error_message TEXT,
                created_at TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=("Inicializa o banco de ingest_logs"))

    parser.add_argument(
        "--db",
        default=str(DATA_DIR / "data.db"),
        help=("Caminho para o arquivo .db"),
    )

    args = parser.parse_args()
    init_db(args.db)
    print(f"Banco de ingest inicializado em: {args.db}")
