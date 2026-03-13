from __future__ import annotations

import contextlib
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from src.db import snapshots as snapshots_db
from src.utils.checksums import sha256_file


def get_retention_days() -> int:
    """Return snapshot retention period in days from environment.

    Reads the ``SNAPSHOT_RETENTION_DAYS`` environment variable and converts
    it to an integer.  If the variable is missing or cannot be parsed as an
    integer, the function falls back to the default of 90 days.

    Returns
    -------
    int
        Number of retention days (default 90).  No parameters; this function
        has the side effect of reading from ``os.environ``.
    """
    raw = os.getenv("SNAPSHOT_RETENTION_DAYS", "90").strip()
    try:
        days = int(raw)
        if days <= 0:
            return 90
        return days
    except ValueError:
        return 90


def find_purge_candidates(
    conn: sqlite3.Connection,
    older_than_days: int,
) -> list[dict[str, object]]:
    """Return metadata rows of snapshots eligible for purging.

    The function queries the ``snapshots`` table for records whose
    ``created_at`` timestamp is older than the UTC cutoff computed from
    ``older_than_days``.  Only non-archived snapshots with a non-null
    ``snapshot_path`` are considered.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open SQLite connection to the metadata database.
    older_than_days : int
        Age threshold in days; snapshots older than this are candidates.

    Returns
    -------
    list of dict
        Each dict contains keys ``id``, ``path`` (snapshot_path),
        ``ticker``, ``created_at``, ``size_bytes``, and ``checksum``.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    cur = conn.cursor()
    _ = cur.execute(
        "SELECT id, snapshot_path AS path, ticker, created_at, size_bytes, checksum "
        "FROM snapshots WHERE archived = 0 AND snapshot_path IS NOT NULL "
        "AND created_at < ? ORDER BY created_at ASC",
        (cutoff.isoformat(),),
    )
    rows = cast(list[tuple[object, ...]], cur.fetchall())
    cols = [col[0] for col in cur.description]
    return [dict(zip(cols, row, strict=False)) for row in rows]


def archive_snapshots(
    conn: sqlite3.Connection,
    snapshot_ids: list[str],  # IDs are stored as TEXT in the DB
    archive_dir: Path,
) -> list[dict[str, object]]:
    """Copy snapshots to an archive directory and mark them archived.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open connection to the metadata database.
    snapshot_ids : list[str]
        List of snapshot IDs (TEXT) that should be archived.
    archive_dir : Path
        Destination directory where snapshot files will be copied.

    Returns
    -------
    list of dict
        Each dict has keys ``id``, ``path`` (original location),
        ``archived_path`` (destination copy or None on failure),
        ``checksum_ok`` (bool), and optionally ``error`` if an OSError
        occurred during copy.

    Side effects
    ------------
    The function creates ``archive_dir`` if missing, copies each snapshot
    file there with a prefix of the ID, computes a SHA-256 checksum of the
    copy, and updates the database row by setting ``archived = 1`` and
    ``archived_at`` (commit occurs at the end).  Checksum mismatches do not
    prevent the database flag from being set; the design assumes even a
    mismatched file should be marked archived and ``checksum_ok`` recorded in
    the results for later inspection.
    """
    if not snapshot_ids:
        return []

    archive_dir.mkdir(parents=True, exist_ok=True)
    placeholders = ",".join("?" * len(snapshot_ids))
    query = (
        "SELECT id, snapshot_path, checksum FROM snapshots "
        f"WHERE id IN ({placeholders})"
    )
    cur = conn.cursor()
    # ensure IDs are str for consistency with DB schema
    str_ids = [str(i) for i in snapshot_ids]
    _ = cur.execute(query, str_ids)
    rows = cast(list[tuple[object, object, object]], cur.fetchall())

    results: list[dict[str, object]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for snapshot_id, raw_path, expected_checksum in rows:
        source_path = Path(str(raw_path))
        archived_path = archive_dir / f"{snapshot_id}_{source_path.name}"
        try:
            _ = shutil.copy2(source_path, archived_path)
        except OSError as exc:  # could be missing/unreadable
            # continue processing other snapshots but mark failure
            results.append(
                {
                    "id": snapshot_id,
                    "path": str(source_path),
                    "archived_path": None,
                    "checksum_ok": False,
                    "error": str(exc),
                }
            )
            continue

        actual_checksum = sha256_file(archived_path)
        checksum_ok = actual_checksum == str(expected_checksum or "")

        # Only mark row as archived when we have a matching checksum. This avoids
        # hiding cases where the snapshot copy does not match metadata.
        if checksum_ok:
            _ = cur.execute(
                "UPDATE snapshots SET archived = 1, archived_at = ? WHERE id = ?",
                (now_iso, snapshot_id),
            )

        results.append(
            {
                "id": snapshot_id,
                "path": str(source_path),
                "archived_path": str(archived_path),
                "checksum_ok": checksum_ok,
            }
        )

    conn.commit()
    return results


def delete_snapshots(
    conn: sqlite3.Connection,
    snapshot_ids: list[str],  # string IDs matching TEXT column in DB
) -> list[dict[str, object]]:
    """Remove snapshot files from disk and delete DB records.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open connection against the metadata database.
    snapshot_ids : list[str]
        List of snapshot identifiers (stored as TEXT in the `snapshots` table)
        to be deleted.

    Returns
    -------
    list[dict[str, object]]
        Each entry contains ``id`` (the snapshot ID), ``path`` (original
        filesystem path) and ``deleted`` (bool indicating whether the CSV file
        no longer exists on disk).

    Side effects
    ------------
    The function attempts to unlink the CSV file and its accompanying
    ``.checksum`` file for each snapshot, suppressing any ``OSError``
    encountered while doing so.  After filesystem cleanup it calls
    :func:`src.db.snapshots.delete_snapshots` to remove rows from the database
    (ids are coerced to strings).  Errors during unlinking do not abort the
    overall operation; they are simply omitted from the returned ``deleted``
    flag.
    """
    if not snapshot_ids:
        return []

    placeholders = ",".join("?" * len(snapshot_ids))
    cur = conn.cursor()
    _ = cur.execute(
        f"SELECT id, snapshot_path FROM snapshots WHERE id IN ({placeholders})",
        snapshot_ids,
    )
    rows = cast(list[tuple[object, object]], cur.fetchall())

    results: list[dict[str, object]] = []
    for snapshot_id, raw_path in rows:
        csv_path = Path(str(raw_path))
        with contextlib.suppress(OSError):
            csv_path.unlink()
        checksum_path = csv_path.with_name(f"{csv_path.name}.checksum")
        with contextlib.suppress(OSError):
            checksum_path.unlink()

        deleted = not csv_path.exists()
        results.append(
            {
                "id": snapshot_id,
                "path": str(csv_path),
                "deleted": deleted,
            }
        )

    ids_as_str = [str(snapshot_id) for snapshot_id in snapshot_ids]
    _ = snapshots_db.delete_snapshots(ids_as_str, conn=conn)
    return results
