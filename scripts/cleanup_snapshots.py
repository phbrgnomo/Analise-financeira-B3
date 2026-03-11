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
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_db(db_path: Path) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dest = db_path.with_suffix(f".bak.{ts}")
    shutil.copy2(db_path, dest)
    return dest


def inspect_and_plan(
    db_path: Path, snapshots_dir: Path, ticker: str | None = None
) -> list[dict[str, Any]]:
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
                "candidate_path": str(candidate),
                "checksum": checksum,
                "action": action,
                "reason": reason,
            }
        )
    return plan


def apply_plan(db_path: Path, plan: list[dict[str, Any]], apply_archive: bool = True):
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
            else:
                if apply_archive:
                    archived_at = datetime.utcnow().isoformat() + "Z"
                    query = (
                        "UPDATE snapshots SET archived = 1, "
                        "archived_at = ? WHERE id = ?"
                    )
                    cur.execute(query, (archived_at, sid))
        conn.commit()
    finally:
        conn.close()


def main() -> None:
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
        "--no-backup",
        action="store_true",
        help="Do not backup DB before applying (not recommended)",
    )

    args = p.parse_args()
    db_path = Path(args.db)
    snapshots_dir = Path(args.snapshots_dir)

    if not db_path.exists():
        print(f"DB not found: {db_path}")
        raise SystemExit(2)

    plan = inspect_and_plan(db_path, snapshots_dir, ticker=args.ticker)

    print(json.dumps({"summary_count": len(plan)}, indent=2))
    if not plan:
        print("No /tmp snapshot_path entries found.")
        return

    print("\nSample plan (first 20):")
    for item in plan[:20]:
        print(json.dumps(item, ensure_ascii=False))

    updates = [i for i in plan if i["action"] == "update_path"]
    archives = [i for i in plan if i["action"] != "update_path"]

    print(f"\nWill update {len(updates)} rows and archive {len(archives)} rows.")

    if args.apply:
        if not args.no_backup:
            bak = backup_db(db_path)
            print(f"Backup created: {bak}")
        apply_plan(db_path, plan, apply_archive=True)
        print("Applied changes to DB.")
    else:
        print("Dry-run: no changes applied. Use --apply to modify DB.")


if __name__ == "__main__":
    main()
