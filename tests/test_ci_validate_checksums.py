"""Tests for CI checksum validation script (Story 2-4).

Verifies all behaviors of the checksum validation script:
- Exit code 0 when all checksums valid
- Exit code 1 when tampered file detected
- Exit code 1 when missing file detected
- Exit code 0 when no snapshots in DB (valid case)
- Output format shows PASS/FAIL status per snapshot
- Summary section with counts (Total, Passed, Failed, Missing)

Script tested: scripts/ci_validate_checksums.py
"""

import pytest

from src import db
from src.db_migrator import apply_migrations
from src.utils.checksums import sha256_file

# The tests no longer create a table by hand; instead we initialize a
# temporary database and run the real migration scripts so the schema stays
# in sync with the application.  Helper above has been removed to avoid
# drift.  See individual tests for migration calls.


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create and migrate a temporary metadata database.

    Patches connection helpers so that any call to ``db.connect`` or the
    lower-level ``_connect`` helpers returns a single connection object.
    Yields
    -------
    sqlite3.Connection, pathlib.Path
        Open connection to the migrated database and the path to the file.
    """
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)
    # close the first handle before opening patched connection to avoid
    # leaving two open handles against the same file
    conn.close()

    test_conn = db.connect(db_path=str(db_path))

    # patch environment and helpers
    monkeypatch.setenv("DB_PATH", str(db_path))
    from src.db import connection

    # redirect both the low-level connector and the public helper so that
    # every part of the application uses our temporary database file.
    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

    yield test_conn, db_path

    test_conn.close()


def _insert_snapshot_metadata(
    conn,
    snap_id: str,
    ticker: str,
    snapshot_path: str,
    checksum: str,
    created_at: str = "2024-01-01T00:00:00Z",
    archived: int = 0,
) -> None:
    """Insert snapshot metadata row into snapshots table."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO snapshots (
            id, ticker, snapshot_path, checksum, created_at, archived
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (snap_id, ticker, snapshot_path, checksum, created_at, archived),
    )
    conn.commit()


def test_valid_checksums_pass(test_db, tmp_path):
    """All snapshot files have valid checksums → exit 0."""
    conn, db_path = test_db

    # 2. Create snapshot files in tmp_path
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()

    snapshot1 = snapshot_dir / "PETR4-20240101T000000Z.csv"
    snapshot1.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,10.0,10.5,9.5,10.2,10.2,1000\n"
    )

    snapshot2 = snapshot_dir / "VALE3-20240101T000000Z.csv"
    snapshot2.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,20.0,20.5,19.5,20.2,20.2,2000\n"
    )

    # 3. Compute correct checksums using sha256_file()
    checksum1 = sha256_file(snapshot1)
    checksum2 = sha256_file(snapshot2)

    # 4. Insert snapshot metadata with correct checksums
    _insert_snapshot_metadata(
        conn,
        snap_id="snap1",
        ticker="PETR4",
        snapshot_path=str(snapshot1),
        checksum=checksum1,
    )

    _insert_snapshot_metadata(
        conn,
        snap_id="snap2",
        ticker="VALE3",
        snapshot_path=str(snapshot2),
        checksum=checksum2,
    )

    # 6. Import and run script's main() function
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # 7. Assertions
    assert exit_code == 0  # All valid → success


def test_tampered_file_fails(test_db, tmp_path, capsys):
    """Modified file after checksum recorded → exit 1."""
    conn, db_path = test_db
    # Create snapshot file (connection already patched by fixture)
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()

    snapshot1 = snapshot_dir / "PETR4-20240101T000000Z.csv"
    snapshot1.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,10.0,10.5,9.5,10.2,10.2,1000\n"
    )

    # Compute correct checksum BEFORE tampering
    checksum1 = sha256_file(snapshot1)

    # Insert snapshot metadata with original checksum
    _insert_snapshot_metadata(
        conn,
        snap_id="snap1",
        ticker="PETR4",
        snapshot_path=str(snapshot1),
        checksum=checksum1,
    )

    # CRITICAL: Tamper with file AFTER checksum recorded in DB
    snapshot1.write_text("TAMPERED DATA - CHECKSUM MISMATCH\n")

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions
    assert exit_code == 1  # Mismatch detected → failure

    # Verify output contains FAIL indicator
    captured = capsys.readouterr()
    output = captured.out
    assert "FAIL:" in output
    assert "Checksum mismatch" in output


def test_missing_file_fails(test_db, tmp_path, capsys):
    """File at snapshot_path doesn't exist → exit 1."""
    conn, db_path = test_db

    # Create snapshot file temporarily
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()

    snapshot1 = snapshot_dir / "PETR4-20240101T000000Z.csv"
    snapshot1.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,10.0,10.5,9.5,10.2,10.2,1000\n"
    )

    # Compute checksum
    checksum1 = sha256_file(snapshot1)

    # Insert snapshot metadata
    _insert_snapshot_metadata(
        conn,
        snap_id="snap1",
        ticker="PETR4",
        snapshot_path=str(snapshot1),
        checksum=checksum1,
    )

    # CRITICAL: Delete file AFTER metadata inserted
    snapshot1.unlink()

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions
    assert exit_code == 1  # Missing file → failure

    # Verify output contains missing file indicator
    captured = capsys.readouterr()
    output = captured.out
    assert "FAIL:" in output
    assert "File not found" in output


def test_no_snapshots_passes(test_db, tmp_path, capsys):
    """Empty DB (no snapshots) → exit 0 (valid case)."""
    conn, db_path = test_db

    # no rows inserted, just run script

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions
    assert exit_code == 0  # Nothing to validate → success

    # Verify output indicates no snapshots
    captured = capsys.readouterr()
    output = captured.out
    assert "No snapshots to validate" in output


def test_output_format_shows_results(test_db, tmp_path, capsys):
    """Stdout contains PASS/FAIL indicators and summary section."""
    conn, db_path = test_db

    # Create snapshot files: 1 valid + 1 tampered
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()

    # Valid file
    snapshot1 = snapshot_dir / "PETR4-20240101T000000Z.csv"
    snapshot1.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,10.0,10.5,9.5,10.2,10.2,1000\n"
    )
    checksum1 = sha256_file(snapshot1)

    # Tampered file
    snapshot2 = snapshot_dir / "VALE3-20240101T000000Z.csv"
    snapshot2.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,20.0,20.5,19.5,20.2,20.2,2000\n"
    )
    checksum2_original = sha256_file(snapshot2)

    # Insert metadata with original checksums
    _insert_snapshot_metadata(
        conn,
        snap_id="snap1",
        ticker="PETR4",
        snapshot_path=str(snapshot1),
        checksum=checksum1,
    )

    _insert_snapshot_metadata(
        conn,
        snap_id="snap2",
        ticker="VALE3",
        snapshot_path=str(snapshot2),
        checksum=checksum2_original,
    )

    # CRITICAL: Tamper with second file AFTER recording checksum
    snapshot2.write_text("TAMPERED DATA\n")

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Capture stdout
    captured = capsys.readouterr()
    output = captured.out

    # Assertions on output format
    assert "PASS:" in output  # At least one PASS (PETR4)
    assert "FAIL:" in output  # At least one FAIL (VALE3)
    assert "Summary:" in output
    assert "Total:" in output
    assert "Passed:" in output
    assert "Failed:" in output
    assert "Missing:" in output

    assert exit_code == 1  # Failed validation → exit 1


def test_archived_snapshots_ignored(test_db, tmp_path):
    """Archived snapshots (archived=1) are NOT validated."""
    conn, db_path = test_db

    # Create snapshot file
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()

    snapshot1 = snapshot_dir / "PETR4-20240101T000000Z.csv"
    snapshot1.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,10.0,10.5,9.5,10.2,10.2,1000\n"
    )
    checksum1 = sha256_file(snapshot1)

    # Insert archived snapshot metadata (archived=1)
    _insert_snapshot_metadata(
        conn,
        snap_id="snap1",
        ticker="PETR4",
        snapshot_path=str(snapshot1),
        checksum=checksum1,
        archived=1,  # CRITICAL: archived snapshot should be ignored
    )

    # Tamper with file (but it should be ignored)
    snapshot1.write_text("TAMPERED BUT ARCHIVED\n")

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions: archived snapshots are not validated
    # Script should show "No snapshots to validate" since all are archived
    assert exit_code == 0  # No validation failures


def test_snapshots_without_checksum_skipped(test_db, tmp_path, capsys):
    """Snapshots without checksum metadata are skipped."""
    conn, db_path = test_db

    # Create snapshot file
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()

    snapshot1 = snapshot_dir / "PETR4-20240101T000000Z.csv"
    snapshot1.write_text(
        "date,open,high,low,close,adj_close,volume\n"
        "2024-01-01,10.0,10.5,9.5,10.2,10.2,1000\n"
    )

    # Insert snapshot metadata WITHOUT checksum (checksum=None)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO snapshots (id, ticker, snapshot_path, created_at, archived)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("snap1", "PETR4", str(snapshot1), "2024-01-01T00:00:00Z", 0),
    )
    conn.commit()

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions: snapshot without checksum is skipped
    captured = capsys.readouterr()
    output = captured.out

    # Should show no snapshots processed (skipped due to missing checksum)
    assert exit_code == 0  # No validation failures
    assert "Total: 0" in output or "No snapshots to validate" in output
