"""Ingest pipeline helpers.

Functions to save provider raw responses to CSV and register ingest metadata
in a local SQLite database (dados/data.db) and optional checksum files.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Union

import pandas as pd

from src.utils.checksums import sha256_file

logger = logging.getLogger(__name__)

# Legacy DB var kept for compatibility; metadata will be written to JSON
DEFAULT_DB = Path("dados/data.db")
DEFAULT_METADATA = Path("metadata/ingest_logs.json")


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


def _ensure_metadata_file(metadata_path: Union[str, Path]) -> None:
    """Ensure metadata directory exists and file is initialized as JSON array.

    The file is created with an empty JSON array if it does not exist.
    """
    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    if not metadata_path.exists():
        # create an empty JSON array atomically
        tmp = metadata_path.with_suffix(".json.tmp")
        tmp.write_text("[]")
        os.replace(str(tmp), str(metadata_path))


def save_raw_csv(
    df: pd.DataFrame,
    provider: str,
    ticker: str,
    ts: Union[str, datetime] = None,
    raw_root: Union[str, Path] = Path("raw"),
    db_path: Union[str, Path] = DEFAULT_DB,
    metadata_path: Union[str, Path] = DEFAULT_METADATA,
    set_permissions: bool = False,
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
        _write_csv_atomic(df_to_save, file_path)
        checksum = _write_checksum(file_path)

        if set_permissions:
            _apply_posix_permissions([file_path, Path(f"{str(file_path)}.checksum")])

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

        try:
            _persist_metadata(metadata, metadata_path)
        except Exception as e_meta:
            _log_metadata_error("Falha ao gravar metadados em JSON", e_meta, metadata)

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
            "metadata_recorded": False,
        }

        # attempt to persist error metadata to JSON as best-effort
        try:
            _persist_metadata(metadata, metadata_path)
        except Exception as e_meta:
            _log_metadata_error("Falha ao gravar metadados de erro em JSON", e_meta,
                                metadata)
        return metadata


# TODO Rename this here and in `save_raw_csv`
def _log_metadata_error(msg: str, e_meta: Exception, metadata: Dict[str, Any]) -> None:
    logger.exception("%s: %s", msg, e_meta)
    metadata["metadata_recorded"] = False
    metadata["metadata_error_message"] = str(e_meta)


# TODO Rename this here and in `save_raw_csv`
def _persist_metadata(
    metadata: Dict[str, Any], metadata_path: Union[str, Path] = DEFAULT_METADATA
) -> None:
    _ensure_metadata_file(metadata_path)
    metadata_path = Path(metadata_path)

    try:
        existing = json.loads(metadata_path.read_text())
        if not isinstance(existing, list):
            existing = []
    except Exception:
        existing = []

    existing.append(metadata)

    tmp = metadata_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    os.replace(str(tmp), str(metadata_path))
    metadata["metadata_recorded"] = True
    metadata["metadata_path"] = str(metadata_path)


def _write_csv_atomic(df: pd.DataFrame, file_path: Union[str, Path]) -> None:
    file_path = Path(file_path)
    filename = file_path.name
    provider_dir = file_path.parent
    fd, tmp = tempfile.mkstemp(prefix=f"{filename}.", dir=str(provider_dir))
    os.close(fd)
    tmp = Path(tmp)
    try:
        df.to_csv(tmp, index=False)
        os.replace(str(tmp), str(file_path))
    finally:
        if tmp.exists() and tmp != file_path:
            with contextlib.suppress(Exception):
                tmp.unlink()


def _write_checksum(file_path: Union[str, Path]) -> str:
    file_path = Path(file_path)
    checksum = sha256_file(file_path)
    checksum_path = Path(f"{str(file_path)}.checksum")
    checksum_path.write_text(checksum)
    return checksum


def _apply_posix_permissions(paths: list[Union[str, Path]]) -> None:
    try:
        if hasattr(os, "chmod"):
            for p in paths:
                os.chmod(str(p), 0o600)
    except Exception:
        logger.exception("Falha ao aplicar permissões aos arquivos")
