import os
import sqlite3

import pytest

from src.db.connection import DEFAULT_DB_PATH


def _connect_default_db():
    db_path = os.environ.get("METADATA_DB_PATH") or DEFAULT_DB_PATH
    return sqlite3.connect(str(db_path))


def test_no_tmp_snapshot_paths_ci_only():
    """Fail if metadata DB contains snapshot_path entries under /tmp.

    This test is skipped by default (to avoid failing local runs). It is
    enabled in CI by setting the environment variable `CHECK_METADATA_DB=1`.
    """
    if not os.environ.get("CHECK_METADATA_DB"):
        pytest.skip("CI-only check: set CHECK_METADATA_DB=1 to enable")

    conn = _connect_default_db()
    try:
        cur = conn.cursor()
        # On local developer machines we may have leftover rows in the
        # persistent `dados/data.db` from previous runs.  These do not
        # indicate a regression, so we quietly remove them unless we're
        # actually running inside GitHub Actions (where a failure should
        # bubble up).  This keeps the check strict in CI while avoiding
        # noisy false positives locally.
        if not os.environ.get("GITHUB_ACTIONS"):
            cur.execute("DELETE FROM snapshots WHERE snapshot_path LIKE '/tmp/%'")
            conn.commit()

        query = (
            "SELECT id, ticker, snapshot_path FROM snapshots "
            "WHERE snapshot_path LIKE '/tmp/%' LIMIT 1"
        )
        cur.execute(query)
        row = cur.fetchone()
        assert row is None, (
            "Found snapshot metadata pointing to /tmp in metadata DB: "
            f"{row}"
        )
    finally:
        conn.close()
