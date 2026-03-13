"""Tests for Story 2-5 — Retention and Purge (src/retention.py).

Verifies all behaviors of snapshot retention and purge functionality:
- get_retention_days() env var parsing with default fallback
- find_purge_candidates() filtering by date and archived status
- archive_snapshots() copies files, validates checksums, marks archived
- delete_snapshots() removes files and DB records
- purge CLI command dry-run and confirm modes
- Edge cases: invalid env vars, missing files, checksum mismatches
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from src import db
from src.db_migrator import apply_migrations
from src.main import app
from src.retention import (
    archive_snapshots,
    delete_snapshots,
    find_purge_candidates,
    get_retention_days,
)
from src.utils.checksums import sha256_file


def test_get_retention_days_default(monkeypatch):
    """Without SNAPSHOT_RETENTION_DAYS env var, returns default 90."""
    monkeypatch.delenv("SNAPSHOT_RETENTION_DAYS", raising=False)
    assert get_retention_days() == 90


def test_get_retention_days_custom(monkeypatch):
    """With SNAPSHOT_RETENTION_DAYS=30, returns 30."""
    monkeypatch.setenv("SNAPSHOT_RETENTION_DAYS", "30")
    assert get_retention_days() == 30


def test_get_retention_days_invalid(monkeypatch):
    """With non-numeric value, returns default 90 (fallback behavior)."""
    monkeypatch.setenv("SNAPSHOT_RETENTION_DAYS", "invalid")
    assert get_retention_days() == 90


def test_find_purge_candidates_returns_old_snapshots(tmp_path):
    """Insert snapshots with old and recent created_at dates.

    Verify only old ones (beyond retention cutoff) are returned.
    """
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)

    # Insert old snapshot (100 days ago)
    old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("1", "PETR4", "/tmp/old.csv", "abc123", 1000, old_date, 0),
    )

    # Insert recent snapshot (10 days ago)
    recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2", "ITUB3", "/tmp/recent.csv", "def456", 2000, recent_date, 0),
    )
    conn.commit()

    # Find candidates older than 90 days
    candidates = find_purge_candidates(conn, older_than_days=90)

    # Only the old snapshot should be returned
    assert len(candidates) == 1
    assert candidates[0]["id"] == "1"
    assert candidates[0]["ticker"] == "PETR4"

    conn.close()


def test_find_purge_candidates_excludes_archived(tmp_path):
    """Insert snapshot with archived=1, verify it does NOT return."""
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)

    # Insert old archived snapshot
    old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("1", "PETR4", "/tmp/old.csv", "abc123", 1000, old_date, 1),
    )

    # Insert old non-archived snapshot
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2", "ITUB3", "/tmp/old2.csv", "def456", 2000, old_date, 0),
    )
    conn.commit()

    candidates = find_purge_candidates(conn, older_than_days=90)

    # Only non-archived snapshot should be returned
    assert len(candidates) == 1
    assert candidates[0]["id"] == "2"
    assert candidates[0]["ticker"] == "ITUB3"

    conn.close()


def test_archive_snapshots_copies_and_marks(tmp_path):
    """Create snapshot file, call archive_snapshots().

    Verify: copy exists in archive_dir, checksum matches, DB archived=1.
    """
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)

    # Create test CSV file
    test_csv = tmp_path / "PETR4_snapshot.csv"
    df = pd.DataFrame(
        {
            "date": ["2023-01-01", "2023-01-02"],
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.0, 9.5],
            "close": [10.5, 11.0],
            "volume": [1000, 1500],
            "ticker": ["PETR4", "PETR4"],
        }
    )
    df.to_csv(test_csv, index=False)

    # Calculate checksum
    checksum = sha256_file(test_csv)

    # Insert snapshot record
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "1",
            "PETR4",
            str(test_csv),
            checksum,
            test_csv.stat().st_size,
            datetime.now(timezone.utc).isoformat(),
            0,
        ),
    )
    conn.commit()

    # Archive the snapshot
    archive_dir = tmp_path / "archive"
    results = archive_snapshots(conn, ["1"], archive_dir)

    # Verify results
    assert len(results) == 1
    assert results[0]["id"] == "1"
    assert results[0]["checksum_ok"] is True

    # Verify archived file exists
    archived_path = archive_dir / f"1_{test_csv.name}"
    assert archived_path.exists()
    assert sha256_file(archived_path) == checksum

    # Verify DB record marked as archived
    row = conn.execute(
        "SELECT archived, archived_at FROM snapshots WHERE id = ?", ("1",)
    ).fetchone()
    assert row[0] == 1, "archived should be 1"
    assert row[1] is not None, "archived_at should be populated"

    conn.close()


def test_archive_snapshots_checksum_mismatch(tmp_path):
    """Simulate checksum mismatch (truncate copied file).

    Verify: still marks archived=1 but reports checksum_ok=False.
    Note: Current implementation marks archived=1 regardless of checksum.
    """
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)

    # Create test CSV file
    test_csv = tmp_path / "PETR4_snapshot.csv"
    df = pd.DataFrame(
        {
            "date": ["2023-01-01"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000],
            "ticker": ["PETR4"],
        }
    )
    df.to_csv(test_csv, index=False)

    # Wrong checksum in DB
    wrong_checksum = "wrong_checksum_value"

    # Insert snapshot record with wrong checksum
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "1",
            "PETR4",
            str(test_csv),
            wrong_checksum,
            test_csv.stat().st_size,
            datetime.now(timezone.utc).isoformat(),
            0,
        ),
    )
    conn.commit()

    # Archive the snapshot
    archive_dir = tmp_path / "archive"
    results = archive_snapshots(conn, ["1"], archive_dir)

    # Verify checksum_ok=False
    assert len(results) == 1
    assert results[0]["checksum_ok"] is False

    # Verify archived=1 still set (current behavior)
    row = conn.execute("SELECT archived FROM snapshots WHERE id = ?", ("1",)).fetchone()
    assert row[0] == 1

    conn.close()


def test_archive_snapshots_missing_source_continues(tmp_path):
    """If the source CSV is missing, the function doesn't raise and reports error."""
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)

    # insert a record pointing to a non-existent file
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "1",
            "PETR4",
            "/nonexistent/path.csv",
            "abc",
            0,
            datetime.now(timezone.utc).isoformat(),
            0,
        ),
    )
    conn.commit()

    archive_dir = tmp_path / "archive"
    results = archive_snapshots(conn, ["1"], archive_dir)

    assert len(results) == 1
    assert results[0]["checksum_ok"] is False
    assert "error" in results[0]

    # DB should not be marked archived because copy failed
    row = conn.execute("SELECT archived FROM snapshots WHERE id = ?", ("1",)).fetchone()
    assert row[0] == 0

    conn.close()


def test_delete_snapshots_removes_files_and_db(tmp_path):
    """Create file + DB record, call delete_snapshots().

    Verify: file removed, DB record removed.
    """
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)

    # Create test CSV file
    test_csv = tmp_path / "PETR4_snapshot.csv"
    df = pd.DataFrame(
        {
            "date": ["2023-01-01"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000],
            "ticker": ["PETR4"],
        }
    )
    df.to_csv(test_csv, index=False)

    # Create checksum sidecar
    checksum_file = Path(str(test_csv) + ".checksum")
    checksum_file.write_text(sha256_file(test_csv))

    # Insert snapshot record
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "1",
            "PETR4",
            str(test_csv),
            "abc123",
            test_csv.stat().st_size,
            datetime.now(timezone.utc).isoformat(),
            0,
        ),
    )
    conn.commit()

    results = delete_snapshots(conn, ["1"])

    # Verify results
    assert len(results) == 1
    assert results[0]["id"] == "1"
    assert results[0]["deleted"] is True

    # Verify files removed
    assert not test_csv.exists()
    assert not checksum_file.exists()

    # Verify DB record removed
    row = conn.execute("SELECT * FROM snapshots WHERE id = ?", ("1",)).fetchone()
    assert row is None

    conn.close()


def test_delete_snapshots_missing_file_no_crash(tmp_path):
    """DB record but file absent on FS.

    Verify: does NOT raise exception (OSError suppressed).
    """
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)

    # Insert snapshot record (no actual file)
    nonexistent_path = tmp_path / "nonexistent.csv"
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "1",
            "PETR4",
            str(nonexistent_path),
            "abc123",
            1000,
            datetime.now(timezone.utc).isoformat(),
            0,
        ),
    )
    conn.commit()

    # Should NOT raise exception
    results = delete_snapshots(conn, ["1"])

    # Verify results (deleted=True because file doesn't exist)
    assert len(results) == 1
    assert results[0]["id"] == "1"
    assert results[0]["deleted"] is True

    # Verify DB record removed
    row = conn.execute("SELECT * FROM snapshots WHERE id = ?", ("1",)).fetchone()
    assert row is None

    conn.close()


def test_purge_dryrun_no_side_effects(purge_test_setup, monkeypatch):
    """Invoke `snapshots purge --dry-run`.

    Verify: DB and FS unchanged.
    """

    test_csv, metadata_db_path, checksum = purge_test_setup

    # Set retention to 90 days (should find the old snapshot)
    monkeypatch.setenv("SNAPSHOT_RETENTION_DAYS", "90")

    # Run purge in dry-run mode
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["snapshots", "purge", "--dry-run"],
    )

    # Verify exit code 0
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    # Verify file still exists
    assert test_csv.exists(), "File should not be deleted in dry-run mode"

    # Verify DB record unchanged
    metadata_conn = db.connect(db_path=str(metadata_db_path))
    row = metadata_conn.execute(
        "SELECT archived FROM snapshots WHERE id = ?", ("1",)
    ).fetchone()
    assert row is not None, "Record should still exist"
    assert row[0] == 0, "archived should still be 0 in dry-run mode"
    metadata_conn.close()


def test_purge_confirm_deletes_candidates(purge_test_setup, monkeypatch):
    """Invoke `snapshots purge --confirm` (without --archive-dir).

    Verify: old snapshots removed from DB and FS.
    """

    test_csv, metadata_db_path, checksum = purge_test_setup

    # Set retention to 90 days
    monkeypatch.setenv("SNAPSHOT_RETENTION_DAYS", "90")

    # Run purge with confirm (delete mode = no archive-dir)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["snapshots", "purge", "--confirm"],
    )

    # Verify exit code 0
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    # Verify file deleted
    assert not test_csv.exists(), "File should be deleted in confirm mode"

    # Verify DB record removed
    metadata_conn = db.connect(db_path=str(metadata_db_path))
    row = metadata_conn.execute(
        "SELECT * FROM snapshots WHERE id = ?", ("1",)
    ).fetchone()
    assert row is None, "Record should be removed"
    metadata_conn.close()


def test_purge_confirm_archives_candidates(purge_test_setup, monkeypatch, tmp_path):
    """Invoke `snapshots purge --confirm --archive-dir`.

    Verify: old snapshots archived and marked archived=1.
    """

    test_csv, metadata_db_path, checksum = purge_test_setup

    # Set retention to 90 days
    monkeypatch.setenv("SNAPSHOT_RETENTION_DAYS", "90")

    # Create archive directory
    archive_dir = tmp_path / "archive"

    # Run purge with confirm and archive-dir (archive mode)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "snapshots",
            "purge",
            "--confirm",
            "--archive-dir",
            str(archive_dir),
        ],
    )

    # Verify exit code 0
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    # Verify archived file exists
    archived_path = archive_dir / f"1_{test_csv.name}"
    assert archived_path.exists(), "Archived file should exist"
    assert sha256_file(archived_path) == checksum

    # Verify DB record marked archived
    metadata_conn = db.connect(db_path=str(metadata_db_path))
    row = metadata_conn.execute(
        "SELECT archived, archived_at FROM snapshots WHERE id = ?", ("1",)
    ).fetchone()
    assert row is not None, "Record should still exist"
    assert row[0] == 1, "archived should be 1"
    assert row[1] is not None, "archived_at should be populated"
    metadata_conn.close()
