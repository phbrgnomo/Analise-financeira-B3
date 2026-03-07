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
    raw = os.getenv("SNAPSHOT_RETENTION_DAYS", "90").strip()
    try:
        return int(raw)
    except ValueError:
        return 90


def find_purge_candidates(
    conn: sqlite3.Connection,
    older_than_days: int,
) -> list[dict[str, object]]:
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
    snapshot_ids: list[int],
    archive_dir: Path,
) -> list[dict[str, object]]:
    if not snapshot_ids:
        return []

    archive_dir.mkdir(parents=True, exist_ok=True)
    placeholders = ",".join("?" * len(snapshot_ids))
    query = (
        "SELECT id, snapshot_path, checksum FROM snapshots "
        f"WHERE id IN ({placeholders})"
    )
    cur = conn.cursor()
    _ = cur.execute(query, snapshot_ids)
    rows = cast(list[tuple[object, object, object]], cur.fetchall())

    results: list[dict[str, object]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for snapshot_id, raw_path, expected_checksum in rows:
        source_path = Path(str(raw_path))
        archived_path = archive_dir / f"{snapshot_id}_{source_path.name}"
        _ = shutil.copy2(source_path, archived_path)

        actual_checksum = sha256_file(archived_path)
        checksum_ok = actual_checksum == str(expected_checksum or "")

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
    snapshot_ids: list[int],
) -> list[dict[str, object]]:
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
