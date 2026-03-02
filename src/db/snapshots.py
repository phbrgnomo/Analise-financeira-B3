"""Snapshot metadata persistence."""

import hashlib
import json
import sqlite3
from typing import Any, Optional

from src.db.connection import _connect
from src.time_utils import now_utc_iso


def get_last_snapshot_payload(
    ticker: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> Optional[str]:
    """Retorna o payload JSON do último snapshot para um ticker.

    Parameters
    ----------
    ticker : str
        Código do ticker (ex: ``"PETR4"``).
    conn : Optional[sqlite3.Connection]
        Conexão SQLite existente (opcional).
    db_path : Optional[str]
        Caminho para o banco (usado se conn não for fornecido).

    Returns
    -------
    Optional[str]
        String JSON do payload ou ``None`` se não encontrado.
    """
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT payload FROM snapshots WHERE ticker = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        if close_conn:
            conn.close()


def record_snapshot_metadata(
    metadata: dict,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> None:
    """Registra um resumo de snapshot/ingest na tabela ``snapshots``.

    Armazena o JSON serializado no campo ``payload`` junto com ``ticker``
    e ``created_at`` para consultas rápidas.
    """
    close_conn = False
    if conn is None:
        conn = _connect(db_path)
        close_conn = True

    try:
        _upsert_snapshot_metadata(conn, metadata)
    finally:
        if close_conn:
            conn.close()


def _upsert_snapshot_metadata(
    conn: sqlite3.Connection, metadata: dict[str, Any]
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY,
            ticker TEXT,
            created_at TEXT,
            payload TEXT
        )
        """
    )
    job_id = (
        metadata.get("job_id")
        or metadata.get("id")
        or hashlib.sha256(
            json.dumps(metadata, sort_keys=True).encode("utf-8")
        ).hexdigest()
    )
    created_at = metadata.get("created_at") or now_utc_iso()
    ticker = metadata.get("ticker") or metadata.get("symbol") or None
    sql = (
        "INSERT OR REPLACE INTO snapshots(id, ticker, created_at, payload) "
        "VALUES (?, ?, ?, ?)"
    )
    cur.execute(
        sql,
        (
            job_id,
            ticker,
            created_at,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    conn.commit()
