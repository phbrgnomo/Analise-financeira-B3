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

from src import db
from src.utils.checksums import sha256_file


def _create_snapshots_table(conn):
    """Create snapshots table with full schema from 0002 migration."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY,
            ticker TEXT,
            created_at TEXT,
            payload TEXT,
            snapshot_path TEXT,
            rows INTEGER,
            checksum TEXT,
            job_id TEXT,
            size_bytes INTEGER,
            archived BOOLEAN DEFAULT 0,
            archived_at TEXT,
            start_date TEXT,
            end_date TEXT,
            rows_count INTEGER
        )
        """
    )
    conn.commit()


def _insert_snapshot_metadata(
    conn,
    snap_id: str,
    ticker: str,
    snapshot_path: str,
    checksum: str,
    created_at: str = "2024-01-01T00:00:00Z",
    archived: int = 0,
):
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


def test_valid_checksums_pass(tmp_path, monkeypatch):
    """All snapshot files have valid checksums → exit 0."""
    # 1. Create test DB with snapshots table
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path=str(db_path))
    _create_snapshots_table(conn)

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

    # 5. Mock db.connect() to return our test DB connection
    test_db_path = str(tmp_path / "test.db")
    test_conn = db.connect(db_path=test_db_path)

    from src.db import connection, snapshots

    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

    # 6. Import and run script's main() function
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # 7. Assertions
    assert exit_code == 0  # All valid → success


def test_tampered_file_fails(tmp_path, monkeypatch, capsys):
    """Modified file after checksum recorded → exit 1."""
    # Create test DB with snapshots table
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path=str(db_path))
    _create_snapshots_table(conn)

    # Create snapshot file
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

    conn.close()

    # CRITICAL: Tamper with file AFTER checksum recorded in DB
    snapshot1.write_text("TAMPERED DATA - CHECKSUM MISMATCH\n")

    # Mock db.connect() to return our test DB connection
    test_db_path = str(tmp_path / "test.db")
    test_conn = db.connect(db_path=test_db_path)

    from src.db import connection, snapshots

    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

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


def test_missing_file_fails(tmp_path, monkeypatch, capsys):
    """File at snapshot_path doesn't exist → exit 1."""
    # Create test DB with snapshots table
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path=str(db_path))
    _create_snapshots_table(conn)

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

    conn.close()

    # CRITICAL: Delete file AFTER metadata inserted
    snapshot1.unlink()

    # Mock db.connect() to return our test DB connection
    test_db_path = str(tmp_path / "test.db")
    test_conn = db.connect(db_path=test_db_path)

    from src.db import connection, snapshots

    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

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


def test_no_snapshots_passes(tmp_path, monkeypatch, capsys):
    """Empty DB (no snapshots) → exit 0 (valid case)."""
    # Create DB with empty snapshots table
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path=str(db_path))
    _create_snapshots_table(conn)
    # DON'T insert any rows
    conn.commit()
    conn.close()

    # Mock db.connect()
    test_db_path = str(tmp_path / "test.db")
    test_conn = db.connect(db_path=test_db_path)

    from src.db import connection, snapshots

    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions
    assert exit_code == 0  # Nothing to validate → success

    # Verify output indicates no snapshots
    captured = capsys.readouterr()
    output = captured.out
    assert "No snapshots to validate" in output


def test_output_format_shows_results(tmp_path, monkeypatch, capsys):
    """Stdout contains PASS/FAIL indicators and summary section."""
    # Create test DB with snapshots table
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path=str(db_path))
    _create_snapshots_table(conn)

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

    conn.close()

    # CRITICAL: Tamper with second file AFTER recording checksum
    snapshot2.write_text("TAMPERED DATA\n")

    # Mock db.connect()
    test_db_path = str(tmp_path / "test.db")
    test_conn = db.connect(db_path=test_db_path)

    from src.db import connection, snapshots

    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

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


def test_archived_snapshots_ignored(tmp_path, monkeypatch):
    """Archived snapshots (archived=1) are NOT validated."""
    # Create test DB with snapshots table
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path=str(db_path))
    _create_snapshots_table(conn)

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

    conn.close()

    # Tamper with file (but it should be ignored)
    snapshot1.write_text("TAMPERED BUT ARCHIVED\n")

    # Mock db.connect()
    test_db_path = str(tmp_path / "test.db")
    test_conn = db.connect(db_path=test_db_path)

    from src.db import connection, snapshots

    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions: archived snapshots are not validated
    # Script should show "No snapshots to validate" since all are archived
    assert exit_code == 0  # No validation failures


def test_snapshots_without_checksum_skipped(tmp_path, monkeypatch, capsys):
    """Snapshots without checksum metadata are skipped."""
    # Create test DB with snapshots table
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path=str(db_path))
    _create_snapshots_table(conn)

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
    conn.close()

    # Mock db.connect()
    test_db_path = str(tmp_path / "test.db")
    test_conn = db.connect(db_path=test_db_path)

    from src.db import connection, snapshots

    monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
    monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

    # Run script
    from scripts.ci_validate_checksums import main

    exit_code = main()

    # Assertions: snapshot without checksum is skipped
    captured = capsys.readouterr()
    output = captured.out

    # Should show no snapshots processed (skipped due to missing checksum)
    assert exit_code == 0  # No validation failures
    assert "Total: 0" in output or "No snapshots to validate" in output
