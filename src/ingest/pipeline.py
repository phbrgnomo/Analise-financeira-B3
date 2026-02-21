"""Ingest pipeline helpers.

Functions to save provider raw responses to CSV and register ingest metadata
in a local SQLite database (dados/data.db) and optional checksum files.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Union

import pandas as pd

from src.utils.checksums import sha256_file

logger = logging.getLogger(__name__)

DEFAULT_DB = Path("dados/data.db")


def _db_initialized(db_path: Union[str, Path]) -> bool:
    """Return True if DB file exists and ingest_logs table is present.

    The pipeline will not create the DB/schema automatically; use
    scripts/init_ingest_db.py to initialize the database prior to running.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='ingest_logs';"
            )
            return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception:
        return False


def save_raw_csv(
    df: pd.DataFrame,
    provider: str,
    ticker: str,
    ts: Union[str, datetime] = None,
    raw_root: Union[str, Path] = Path("raw"),
    db_path: Union[str, Path] = DEFAULT_DB,
) -> Dict[str, Any]:
    """Save DataFrame to raw/<provider>/<ticker>-<ts>.csv and register metadata.

    The function no longer creates the DB or schema. If the DB/schema is not
    present, the CSV and checksum are still written but the metadata is not
    recorded to the SQLite DB. Use scripts/init_ingest_db.py to initialize
    the DB.
    """
    if ts is None:
        ts_dt = datetime.now(timezone.utc)
        ts_str = ts_dt.strftime("%Y%m%dT%H%M%SZ")
    elif isinstance(ts, datetime):
        ts_dt = ts.astimezone(timezone.utc)
        ts_str = ts_dt.strftime("%Y%m%dT%H%M%SZ")
    else:
        ts_str = str(ts)

    raw_root = Path(raw_root)
    provider_dir = raw_root / provider
    provider_dir.mkdir(parents=True, exist_ok=True)

    # deterministic column ordering (stable)
    try:
        df_to_save = df.reindex(sorted(df.columns), axis=1)
    except Exception:
        df_to_save = df.copy()

    filename = f"{ticker}-{ts_str}.csv"
    file_path = provider_dir / filename

    job_id = str(uuid.uuid4())
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    created_at = fetched_at
    rows = len(df_to_save)

    try:
        # write CSV
        df_to_save.to_csv(file_path, index=True)

        # compute checksum
        checksum = sha256_file(file_path)

        # write checksum file next to CSV (e.g. file.csv.checksum)
        checksum_path = Path(f"{str(file_path)}.checksum")
        checksum_path.write_text(checksum)

        metadata = {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": checksum,
            "rows": rows,
            "filepath": str(file_path),
            "status": "success",
            "created_at": created_at,
        }

        # attempt to persist metadata only if DB/schema initialized
        if _db_initialized(db_path):
            try:
                conn = sqlite3.connect(str(db_path))
                try:
                    cur = conn.cursor()
                    sql = (
                        "INSERT INTO ingest_logs ("
                        "job_id, source, fetched_at, raw_checksum, "
                        "rows, filepath, status, error_message, created_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    cur.execute(
                        sql,
                        (
                            job_id,
                            provider,
                            fetched_at,
                            checksum,
                            rows,
                            str(file_path),
                            "success",
                            None,
                            created_at,
                        ),
                    )
                    conn.commit()
                    metadata["db_recorded"] = True
                finally:
                    conn.close()
            except Exception as e_db:
                logger.exception("Falha ao registrar ingest_log: %s", e_db)
                metadata["db_recorded"] = False
                metadata["db_error_message"] = str(e_db)
        else:
            metadata["db_recorded"] = False
            metadata["db_message"] = (
                "Database not initialized; run scripts/init_ingest_db.py to "
                "create ingest_logs table"
            )

        return metadata

    except Exception as e:
        logger.exception("Erro ao salvar raw CSV: %s", e)

        metadata = {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": None,
            "rows": rows,
            "filepath": str(file_path),
            "status": "error",
            "error_message": str(e),
            "created_at": created_at,
            "db_recorded": False,
        }

        # try to record the error if DB/schema initialized
        if _db_initialized(db_path):
            try:
                conn = sqlite3.connect(str(db_path))
                try:
                    cur = conn.cursor()
                    sql = (
                        "INSERT INTO ingest_logs ("
                        "job_id, source, fetched_at, raw_checksum, "
                        "rows, filepath, status, error_message, created_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    )
                    cur.execute(
                        sql,
                        (
                            job_id,
                            provider,
                            fetched_at,
                            None,
                            rows,
                            str(file_path),
                            "error",
                            str(e),
                            created_at,
                        ),
                    )
                    conn.commit()
                    metadata["db_recorded"] = True
                finally:
                    conn.close()
            except Exception as e_db:
                logger.exception("Falha ao registrar ingest_log de erro: %s", e_db)
                metadata["db_db_error"] = str(e_db)
        else:
            metadata["db_message"] = (
                "Database not initialized; run scripts/init_ingest_db.py to "
                "create ingest_logs table"
            )

        return metadata
