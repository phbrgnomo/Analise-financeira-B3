"""Snapshot metadata persistence."""

import hashlib
import json
import sqlite3
from datetime import datetime
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
        "CREATE INDEX IF NOT EXISTS snapshots_ticker_created_at_idx "
        "ON snapshots(ticker, created_at)"
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
        "INSERT OR REPLACE INTO snapshots("
        "id, ticker, created_at, payload, snapshot_path, "
        "rows, checksum, job_id, size_bytes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    cur.execute(
        sql,
        (
            job_id,
            ticker,
            created_at,
            json.dumps(metadata, ensure_ascii=False),
            metadata.get("snapshot_path"),
            metadata.get("rows"),
            metadata.get("checksum"),
            metadata.get("job_id"),
            metadata.get("size_bytes"),
        ),
    )
    conn.commit()


def get_snapshot_metadata(
    snapshot_id: str,
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Retrieve snapshot metadata by ID.

    Parameters
    ----------
    snapshot_id : str
        Snapshot ID to retrieve.
    conn : Optional[sqlite3.Connection]
        Optional SQLite connection.
    db_path : Optional[str]
        Database path (used if conn not provided).

    Returns
    -------
    Optional[dict]
        Snapshot metadata dictionary or None if not found.
    """
    _conn = conn or _connect(db_path)
    try:
        cur = _conn.cursor()
        cur.execute("SELECT * FROM snapshots WHERE id = ? LIMIT 1",
                    (snapshot_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip(
            [col[0] for col in cur.description], row, strict=False
        ))
    finally:
        if conn is None:
            _conn.close()


def list_snapshots(
    ticker: Optional[str] = None,
    *,
    archived: bool = False,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    """List snapshots filtered by ticker and archived status.

    Parameters
    ----------
    ticker : Optional[str]
        Ticker to filter (if None, returns all tickers).
    archived : bool
        Filter by archived status (default False).
    conn : Optional[sqlite3.Connection]
        Optional SQLite connection.
    db_path : Optional[str]
        Database path (used if conn not provided).

    Returns
    -------
    list[dict]
        List of snapshot metadata dictionaries ordered by created_at DESC.
    """
    _conn = conn or _connect(db_path)
    try:
        cur = _conn.cursor()
        archived_int = 1 if archived else 0
        if ticker is None:
            cur.execute(
                "SELECT * FROM snapshots WHERE archived = ? "
                "ORDER BY created_at DESC",
                (archived_int,)
            )
        else:
            cur.execute(
                "SELECT * FROM snapshots WHERE archived = ? AND ticker = ? "
                "ORDER BY created_at DESC",
                (archived_int, ticker)
            )
        rows = cur.fetchall()
        cols = [col[0] for col in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]
    finally:
        if conn is None:
            _conn.close()


def mark_snapshots_archived(
    snapshot_ids: list[str],
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> int:
    """Mark snapshots as archived.

    Parameters
    ----------
    snapshot_ids : list[str]
        List of snapshot IDs to archive.
    conn : Optional[sqlite3.Connection]
        Optional SQLite connection.
    db_path : Optional[str]
        Database path (used if conn not provided).

    Returns
    -------
    int
        Number of rows updated.
    """
    if not snapshot_ids:
        return 0
    _conn = conn or _connect(db_path)
    try:
        cur = _conn.cursor()
        archived_at = datetime.utcnow().isoformat()
        placeholders = ",".join("?" * len(snapshot_ids))
        cur.execute(
            f"UPDATE snapshots SET archived = 1, archived_at = ? "
            f"WHERE id IN ({placeholders})",
            (archived_at, *snapshot_ids)
        )
        _conn.commit()
        return cur.rowcount
    finally:
        if conn is None:
            _conn.close()


def delete_snapshots(
    snapshot_ids: list[str],
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> int:
    """Delete snapshots by ID.

    Parameters
    ----------
    snapshot_ids : list[str]
        List of snapshot IDs to delete.
    conn : Optional[sqlite3.Connection]
        Optional SQLite connection.
    db_path : Optional[str]
        Database path (used if conn not provided).

    Returns
    -------
    int
        Number of rows deleted.
    """
    if not snapshot_ids:
        return 0
    _conn = conn or _connect(db_path)
    try:
        cur = _conn.cursor()
        placeholders = ",".join("?" * len(snapshot_ids))
        cur.execute(
            f"DELETE FROM snapshots WHERE id IN ({placeholders})",
            snapshot_ids
        )
        _conn.commit()
        return cur.rowcount
    finally:
        if conn is None:
            _conn.close()


def get_snapshot_by_path(
    snapshot_path: str,
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Retrieve snapshot metadata by snapshot_path.

    Parameters
    ----------
    snapshot_path : str
        Snapshot path to retrieve.
    conn : Optional[sqlite3.Connection]
        Optional SQLite connection.
    db_path : Optional[str]
        Database path (used if conn not provided).

    Returns
    -------
    Optional[dict]
        Snapshot metadata dictionary or None if not found.
    """
    _conn = conn or _connect(db_path)
    try:
        cur = _conn.cursor()
        cur.execute(
            "SELECT * FROM snapshots WHERE snapshot_path = ? LIMIT 1",
            (snapshot_path,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip(
            [col[0] for col in cur.description], row, strict=False
        ))
    finally:
        if conn is None:
            _conn.close()
