"""Inspeção e limpeza segura de entradas de snapshots órfãos (/tmp).

Uso:
  python scripts/cleanup_snapshots.py --db dados/data.db --dry-run

O script lista rows em `snapshots` cujo `snapshot_path` começa com
`/tmp/`. Em modo dry-run apenas reporta ações sugeridas. No modo
`--apply` realiza atualizações (aplica somente mudanças específicas
seguras: atualizar `snapshot_path` para `snapshots/<basename>` quando o
arquivo existir e o checksum bater; caso contrário marca como archived).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.logging_config import configure_logging
from src.time_utils import now_utc_iso

# configure a basic structured logger for the script
configure_logging()
logger = logging.getLogger(__name__)


def sha256_file(path: Path) -> str:
    """Compute SHA-256 checksum of a file.

    Parameters:
        path (Path): Path to the file to hash.

    Returns:
        str: Hexadecimal SHA-256 digest of the file contents.

    Raises:
        OSError: Propagated if the file cannot be opened or read.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_db(db_path: Path) -> Path:
    """Create a timestamped copy of the database file.

    Parameters:
        db_path (Path): Path to the original database.

    Returns:
        Path: Path to the created backup file.

    Raises:
        OSError: If the copy operation fails.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = db_path.with_suffix(f".bak.{ts}")
    shutil.copy2(db_path, dest)
    return dest


def inspect_and_plan(
    db_path: Path, snapshots_dir: Path, ticker: str | None = None
) -> list[dict[str, Any]]:
    """Query `/tmp/` entries and determine remediation actions.

    Parameters:
        db_path (Path): Location of the SQLite database.
        snapshots_dir (Path): Directory holding project snapshots for file
            candidate checks.
        ticker (str | None): Optional ticker filter; when provided only rows
            matching this ticker are examined.

    Returns:
        list[dict[str, Any]]: A plan describing each row and suggested
        action (`update_path` or `archive`) along with reasoning.

    Raises:
        sqlite3.DatabaseError: On DB access problems.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        if ticker:
            cur.execute(
                "SELECT id, ticker, snapshot_path, checksum FROM snapshots "
                "WHERE snapshot_path LIKE '/tmp/%' AND ticker = ?",
                (ticker,),
            )
        else:
            cur.execute(
                "SELECT id, ticker, snapshot_path, checksum FROM snapshots "
                "WHERE snapshot_path LIKE '/tmp/%'",
            )
        rows = cur.fetchall()
    finally:
        conn.close()

    plan: list[dict[str, Any]] = []
    for row in rows:
        sid, tkr, path_str, checksum = row
        path = Path(path_str)
        basename = path.name
        candidate = snapshots_dir / basename
        action = "archive"
        reason = "default: file missing or checksum mismatch"
        if candidate.exists():
            try:
                actual = sha256_file(candidate)
            except OSError:
                actual = None
            if actual and checksum and actual == checksum:
                action = "update_path"
                reason = "found matching file in snapshots dir"
            else:
                reason = "found file but checksum differs"

        plan.append(
            {
                "id": sid,
                "ticker": tkr,
                "old_path": str(path),
                "candidate_path": str(candidate.resolve(strict=False)),
                "checksum": checksum,
                "action": action,
                "reason": reason,
            }
        )
    return plan


def apply_plan(db_path: Path, plan: list[dict[str, Any]], apply_archive: bool = True):
    """Execute the inspection plan against the database.

    Parameters:
        db_path (Path): Path to the SQLite database to update.
        plan (list[dict]): Plan as returned by :func:`inspect_and_plan`.
        apply_archive (bool): If True, rows not eligible for path updates
            will be marked archived.

    Returns:
        None

    Raises:
        sqlite3.DatabaseError: Propagated from SQL execution.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        for item in plan:
            sid = item["id"]
            if item["action"] == "update_path":
                new_path = item["candidate_path"]
                cur.execute(
                    "UPDATE snapshots SET snapshot_path = ? WHERE id = ?",
                    (new_path, sid),
                )
            elif apply_archive:
                # use project-wide UTC timestamp formatter to ensure consistent
                # stored format across snapshot rows
                archived_at = now_utc_iso()
                query = (
                    "UPDATE snapshots SET archived = 1, archived_at = ? WHERE id = ?"
                )
                cur.execute(query, (archived_at, sid))
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    """Command‑line entry point for snapshot cleanup.

    Parses CLI arguments, computes an inspection plan, prints a summary, and
    optionally applies the plan (with backup). Exits with code 2 if the
    database path is missing.

    Returns:
        None
    """
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="dados/data.db", help="Path to DB")
    p.add_argument(
        "--snapshots-dir",
        default="snapshots",
        help="Project snapshots dir to check for candidates",
    )
    p.add_argument("--ticker", help="Filter by ticker (optional)")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates (without this flag only dry-run)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Report actions without applying changes",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not backup DB before applying (not recommended)",
    )

    args = p.parse_args()
    if args.apply and args.dry_run:
        p.error("Cannot specify both --apply and --dry-run")
    apply_changes = args.apply and not args.dry_run

    db_path = Path(args.db)
    snapshots_dir = Path(args.snapshots_dir)

    if not db_path.exists():
        logger.warning("DB not found: %s", db_path)
        raise SystemExit(2)

    plan = inspect_and_plan(db_path, snapshots_dir, ticker=args.ticker)

    logger.info(json.dumps({"summary_count": len(plan)}, indent=2))
    if not plan:
        logger.info("No /tmp snapshot_path entries found.")
        return

    logger.info("\nSample plan (first 20):")
    for item in plan[:20]:
        logger.info(json.dumps(item, ensure_ascii=False))

    updates = [i for i in plan if i["action"] == "update_path"]
    archives = [i for i in plan if i["action"] != "update_path"]

    # report planned actions using separate arguments to avoid long
    # formatted strings triggering the line‑length linter.
    logger.info(
        "\nWill update %d rows and archive %d rows.",
        len(updates),
        len(archives),
    )

    if apply_changes:
        if not args.no_backup:
            bak = backup_db(db_path)
            logger.info("Backup created: %s", bak)
        apply_plan(db_path, plan, apply_archive=True)
        logger.info("Applied changes to DB.")
    else:
        logger.info("Dry-run: no changes applied. Use --apply to modify DB.")


if __name__ == "__main__":
    main()
