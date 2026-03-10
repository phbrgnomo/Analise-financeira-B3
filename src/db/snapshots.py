"""Snapshot metadata persistence."""


import hashlib
import json
import re
import sqlite3
from typing import Any, Optional

from src.db.connection import _connect
from src.time_utils import now_utc_iso


def _extract_date_range_from_payload(  # noqa: C901 - multiple fallback strategies
    metadata: dict[str, Any],
) -> tuple[str, str]:
    """Extract start/end dates from snapshot metadata.

    The function attempts to determine a ``(start, end)`` pair in
    ``YYYY-MM-DD`` form by probing the provided metadata dictionary using a
    sequence of fallback strategies:

    1. Look for explicit keys ``"start"``/``"start_date"`` and
       ``"end"``/``"end_date"`` at the top level of ``metadata``.
    2. If missing, and ``metadata["payload"]`` is a JSON string or dict,
       parse it and repeat step 1 on the resulting object.
    3. Finally, inspect ``metadata.get("snapshot_path")`` for any
       substrings matching either ``YYYY-MM-DD`` or ``YYYYMMDD``; the first
       match becomes ``start`` and the second (if present) becomes ``end``.

    A nested helper ``_normalize_date_string`` converts ``YYYYMMDD`` inputs to
    ``YYYY-MM-DD``.  When no date is found for a boundary, the returned value
    is the empty string.  This lenient behavior allows callers to handle
    unspecified ranges gracefully.

    Parameters
    ----------
    metadata : dict[str, Any]
        Arbitrary snapshot metadata; keys may include
        ``ticker``, ``snapshot_path``, ``payload`` (JSON), and date fields as
        described above.

    Returns
    -------
    tuple[str, str]
        ``(start, end)`` strings normalized to ``YYYY-MM-DD`` or ``""`` when
        unspecified.

    Examples
    --------
    >>> _extract_date_range_from_payload({"snapshot_path": "/foo/20230101"})
    ("2023-01-01", "")
    >>> _extract_date_range_from_payload({"payload": '{"start": "2023-01-01",
    "end_date": "2023-01-02"}'})
    ("2023-01-01", "2023-01-02")
    """
    def _normalize_date_string(date_str: str) -> str:
        """Normalize date strings to ``YYYY-MM-DD`` format.

        Accepts either ``YYYY-MM-DD`` or ``YYYYMMDD`` and returns the
        dashed variant. If the incoming string doesn’t match either pattern
        it is returned unchanged (allowing unknown formats to pass through).
        """
        date_str = date_str.strip()
        if not date_str:
            return date_str
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
            return date_str
        if re.fullmatch(r"\d{8}", date_str):
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    start = str(metadata.get("start") or metadata.get("start_date") or "")
    end = str(metadata.get("end") or metadata.get("end_date") or "")
    if start and end:
        return _normalize_date_string(start), _normalize_date_string(end)

    payload_obj: dict[str, Any] = {}
    payload = metadata.get("payload")
    if isinstance(payload, dict):
        payload_obj = payload
    elif isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                payload_obj = parsed
        except json.JSONDecodeError:
            payload_obj = {}

    if not start:
        start = str(payload_obj.get("start") or payload_obj.get("start_date") or "")
    if not end:
        end = str(payload_obj.get("end") or payload_obj.get("end_date") or "")
    if start and end:
        return _normalize_date_string(start), _normalize_date_string(end)

    snapshot_path = str(metadata.get("snapshot_path") or "")
    date_matches = re.findall(r"\d{4}-\d{2}-\d{2}|\d{8}", snapshot_path)
    normalized_matches = [_normalize_date_string(m) for m in date_matches]
    if not start and normalized_matches:
        start = normalized_matches[0]
    if not end and len(normalized_matches) >= 2:
        end = normalized_matches[1]
    return start, end


def _build_stable_snapshot_job_id(metadata: dict[str, Any]) -> str:
    """Produce a deterministic job ID for a snapshot.

    Parameters
    ----------
    metadata : dict[str, Any]
        Arbitrary snapshot metadata.  This function looks for ``ticker`` or
        ``symbol`` keys (falling back to empty string if neither is present)
        as well as any date range information obtained via
        :func:`_extract_date_range_from_payload` (which inspects the payload
        or the snapshot_path).  The date strings are normalized internally
        (see ``_extract_date_range_from_payload`` for details).

    Returns
    -------
    str
        A SHA‑256 hex digest computed from the string ``"ticker_start_end"``.
        Using a hash means the identifier remains stable across runs even if
        the original key values are long or vary in formatting.

    Notes
    -----
    - Missing ticker/symbol collapses to the empty string.
    - This helper is used by the metadata upsert logic to avoid generating
      duplicate records for the same underlying snapshot range.
    """
    ticker = str(metadata.get("ticker") or metadata.get("symbol") or "").strip()
    start, end = _extract_date_range_from_payload(metadata)
    stable_key = f"{ticker}_{start}_{end}"
    return hashlib.sha256(stable_key.encode("utf-8")).hexdigest()


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
    metadata: dict[str, Any],
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
        or _build_stable_snapshot_job_id(metadata)
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
            job_id,
            metadata.get("size_bytes"),
        ),
    )
    conn.commit()


def get_snapshot_metadata(
    snapshot_id: str,
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
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
) -> list[dict[str, Any]]:
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
        return _extracted_from_list_snapshots_28(_conn, archived, ticker)
    finally:
        if conn is None:
            _conn.close()


# TODO Rename this here and in `list_snapshots`
def _extracted_from_list_snapshots_28(_conn, archived, ticker):
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
        return _extracted_from_mark_snapshots_archived_27(_conn, snapshot_ids)
    finally:
        if conn is None:
            _conn.close()


# TODO Rename this here and in `mark_snapshots_archived`
def _extracted_from_mark_snapshots_archived_27(_conn, snapshot_ids):
    cur = _conn.cursor()
    # use shared helper to ensure consistent UTC ISO format
    archived_at = now_utc_iso()
    placeholders = ",".join("?" * len(snapshot_ids))
    cur.execute(
        f"UPDATE snapshots SET archived = 1, archived_at = ? "
        f"WHERE id IN ({placeholders})",
        (archived_at, *snapshot_ids)
    )
    _conn.commit()
    return cur.rowcount


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
) -> Optional[dict[str, Any]]:
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
