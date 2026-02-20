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


def _ensure_db_table(db_path: Union[str, Path]) -> None:
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


def save_raw_csv(
    df: pd.DataFrame,
    provider: str,
    ticker: str,
    ts: Union[str, datetime] = None,
    raw_root: Union[str, Path] = Path("raw"),
    db_path: Union[str, Path] = DEFAULT_DB,
) -> Dict[str, Any]:
    """Save DataFrame to raw/<provider>/<ticker>-<ts>.csv and register metadata.

    Returns a metadata dict with keys: job_id, source, fetched_at, raw_checksum,
    rows, filepath, status and optional error_message on failure.
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

    # ensure DB table exists
    _ensure_db_table(db_path)

    try:
        # write CSV
        df_to_save.to_csv(file_path, index=True)

        # compute checksum
        checksum = sha256_file(file_path)

        # write checksum file next to CSV (e.g. file.csv.checksum)
        checksum_path = Path(f"{str(file_path)}.checksum")
        checksum_path.write_text(checksum)

        # persist metadata in sqlite
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
        finally:
            conn.close()

        return {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": checksum,
            "rows": rows,
            "filepath": str(file_path),
            "status": "success",
            "created_at": created_at,
        }
    except Exception as e:
        logger.exception("Erro ao salvar raw CSV: %s", e)
        # attempt to record failure in DB
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
            finally:
                conn.close()
        except Exception:
            logger.exception("Falha ao registrar ingest_log de erro.")

        return {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": None,
            "rows": rows,
            "filepath": str(file_path),
            "status": "error",
            "error_message": str(e),
            "created_at": created_at,
        }
