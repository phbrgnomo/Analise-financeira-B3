from __future__ import annotations

# Snapshot retention helpers.
#
# This module owns the logic for identifying stale snapshot metadata entries
# and acting on them (archiving, deleting). The intended data flow is:
#
# 1. `find_purge_candidates` is called by CLI or other orchestration code to
#    fetch rows that are older than the retention cutoff (typically based on
#    `SNAPSHOT_RETENTION_DAYS`).
# 2. `archive_snapshots` can be used to copy snapshot files to an archive
#    directory and mark the corresponding metadata rows as archived.
# 3. `delete_snapshots` removes files from disk and deletes metadata rows.
#
# The CLI surface (`src.snapshot_cli`) uses these helpers to implement a
# safe purge workflow: listing candidates with `--dry-run`, requiring
# `--confirm` to apply changes, and optionally archiving instead of deleting.
#
# Note: `archive_snapshots` reports checksum mismatch via the returned
# `checksum_ok` flag. The row is always marked as archived to avoid treating
# it as still active.
import contextlib
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict, cast

from src.db import snapshots as snapshots_db
from src.utils.checksums import sha256_file


class ArchivedSnapshotResult(TypedDict, total=False):
    """Result row returned by :func:`archive_snapshots`.

    Fields are intentionally permissive to simplify call-sites that treat the
    output as a generic mapping.
    """

    id: str
    path: str
    archived_path: str | None
    checksum_ok: bool | None
    error: str


logger = logging.getLogger(__name__)


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

    Raises
    ------
    ValueError
        If ``older_than_days`` is negative.
    """
    if older_than_days < 0:
        raise ValueError("older_than_days must be non-negative")

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
) -> list[ArchivedSnapshotResult]:
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
        ``checksum_ok`` (bool | None; ``None`` indicates the checksum could
        not be verified due to missing metadata), and optionally ``error``
        if an OSError occurred during copy.

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

    results: list[ArchivedSnapshotResult] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    created_archives: list[Path] = []

    try:
        # Ensure we can rollback if something goes wrong (e.g. commit fails).
        if not conn.in_transaction:
            conn.execute("BEGIN")

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

            created_archives.append(archived_path)

            actual_checksum = sha256_file(archived_path)
            if expected_checksum is None:
                checksum_ok = None
            else:
                checksum_ok = actual_checksum == str(expected_checksum)

            # Regardless of checksum result (including unverifiable cases), mark the
            # row as archived so that the purge logic does not repeatedly attempt to
            # process the same entry. The `checksum_ok` flag allows callers to
            # detect and log mismatches or missing metadata.
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
    except Exception:
        # Ensure DB state is consistent and remove partially-created archives.
        logger.exception(
            "archive_snapshots failed; rolling back DB changes and removing copies"
        )
        with contextlib.suppress(Exception):
            conn.rollback()

        for p in created_archives:
            with contextlib.suppress(OSError):
                p.unlink()

        raise

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

    str_ids = [str(snapshot_id) for snapshot_id in snapshot_ids]
    placeholders = ",".join("?" * len(str_ids))
    cur = conn.cursor()
    _ = cur.execute(
        f"SELECT id, snapshot_path FROM snapshots WHERE id IN ({placeholders})",
        str_ids,
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

    _ = snapshots_db.delete_snapshots(str_ids, conn=conn)
    return results
