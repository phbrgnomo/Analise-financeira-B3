"""Tests for Story 2-2 — Checksum Metadata Registration.

Verifies all behaviors of snapshot metadata recording:
- Metadata registered after pipeline snapshot with all fields populated
- Checksum matches sha256_file() of generated CSV
- Checksum sidecar file exists next to CSV
- Metadata idempotent on rerun (INSERT OR REPLACE semantics)
- Metadata rows count matches DataFrame length
- Metadata size_bytes matches file size
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from src import db
from src.db_migrator import apply_migrations
from src.main import app
from src.utils.checksums import sha256_file


@pytest.fixture
def snapshot_test_db(tmp_path, sample_db, monkeypatch):
    """Prepare a fresh metadata DB and patch connections.

    Returns
    -------
    pathlib.Path
        Path to the metadata database file.
    """
    # ``sample_db`` contains price rows used by snapshot tests.  After
    # refactoring price helpers to use ``src.db.connection.connect`` this
    # fixture must intercept that public connector so snapshot generation
    # reads from the in-memory sample database instead of the real file.
    from src.db import connection

    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)
    conn.close()

    # patch connection.connect to route price reads to sample_db
    monkeypatch.setattr(connection, "connect", lambda db_path=None: sample_db)
    # ``prices.read_prices`` imported the connector at import-time; patch
    # that name as well so CLI commands pick up our sample DB.
    from src.db import prices
    monkeypatch.setattr(prices, "connect", lambda db_path=None: sample_db)

    # Force all metadata writes produced by the CLI to land in our
    # explicitly-created test database.  We patch ``db.connect`` separately so
    # metadata operations are isolated from price reads.
    original_db_connect = db.connect

    def _mock_db_connect(db_path_arg=None, **kw):
        # If the caller does not specify a path or explicitly asks for our
        # test DB, return a connection to ``db_path``.  Otherwise forward
        # the request unmodified so other tests (e.g. price reads) behave
        # normally.
        if db_path_arg is None or str(db_path_arg) == str(db_path):
            return original_db_connect(db_path=str(db_path))
        return original_db_connect(db_path=db_path_arg, **kw)

    monkeypatch.setattr(db, "connect", _mock_db_connect)

    return db_path


def test_snapshot_path_under_temp_is_sanitized(snapshot_test_db, tmp_path, monkeypatch):
    """Stats that /tmp paths are rewritten to basename when metadata is saved.

    Calling the database helper directly lets us avoid running the whole CLI and
    focuses the test on the normalization step.  This is the behavior that
    prevents ``/tmp`` references from triggering the CI guard in
    ``test_no_tmp_snapshot_paths_ci_only``.
    """
    tempdir = Path(tempfile.gettempdir())
    tempdir.mkdir(parents=True, exist_ok=True)
    snap = tempdir / "PETR4_snapshot.csv"
    snap.write_text("ticker,date,open,high,low,close,volume,adj_close\n")

    metadata = {
        "ticker": "PETR4",
        "snapshot_path": str(snap),
        "rows": 0,
        "checksum": "deadbeef",
        "created_at": "2026-01-01T00:00:00Z",
        "size_bytes": 0,
        "job_id": "job-temp",
    }
    from src.db import snapshots

    conn = db.connect(db_path=str(snapshot_test_db))
    snapshots.record_snapshot_metadata(metadata, conn=conn)

    cur = conn.cursor()
    cur.execute("SELECT snapshot_path FROM snapshots WHERE job_id = ?", ("job-temp",))
    row = cur.fetchone()
    assert row is not None
    stored = row[0]
    assert not stored.startswith(tempdir.as_posix()), (
        "Stored path should not keep the /tmp prefix"
    )
    assert stored == "PETR4_snapshot.csv"
    conn.close()


def test_metadata_registered_after_snapshot(snapshot_test_db, tmp_path):
    """After pipeline snapshot, DB has row with all fields populated."""
    db_path = snapshot_test_db

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}"

    metadata = db.list_snapshots(ticker="PETR4", db_path=str(db_path))
    assert len(metadata) >= 1, "Expected at least one metadata row"

    row = metadata[0]
    assert row["id"] is not None, "id field should be populated"
    assert row["ticker"] == "PETR4", "ticker should match"
    assert row["snapshot_path"] is not None, "snapshot_path should be populated"
    assert (
        row["snapshot_path"].startswith("PETR4")
        or "/tmp/" not in row["snapshot_path"]
    ), (
        "metadata path should not include raw /tmp prefix"
    )
    assert row["created_at"] is not None, "created_at should be populated"
    assert row["rows"] is not None, "rows field should be populated"
    assert row["checksum"] is not None, "checksum field should be populated"
    assert row["job_id"] is not None, "job_id field should be populated"


def test_checksum_matches_sha256_file(snapshot_test_db, tmp_path, monkeypatch):
    """checksum in DB equals sha256_file() of generated CSV."""

    db_path = snapshot_test_db

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0

    csv_path = output_dir / "PETR4_snapshot.csv"
    assert csv_path.exists(), "CSV file should exist"

    expected_checksum = sha256_file(csv_path)

    metadata = db.list_snapshots(ticker="PETR4", db_path=str(db_path))
    assert len(metadata) >= 1
    recorded_checksum = metadata[0]["checksum"]

    assert (
        recorded_checksum == expected_checksum
    ), f"DB checksum {recorded_checksum} != file checksum {expected_checksum}"


def test_checksum_sidecar_written(snapshot_test_db, tmp_path, monkeypatch):
    """.checksum sidecar file exists next to CSV."""


    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0

    csv_path = output_dir / "PETR4_snapshot.csv"
    checksum_file = Path(f"{str(csv_path)}.checksum")

    assert checksum_file.exists(), (
        f"Checksum sidecar file should exist: {checksum_file}"
    )
    assert checksum_file.stat().st_size > 0, "Checksum file should not be empty"


def test_metadata_idempotent_on_rerun(sample_db, tmp_path, monkeypatch):
    """Running pipeline snapshot twice → single row in DB (INSERT OR REPLACE)."""
    from src.db import prices

    # Create test DB and seed with PETR4 data from sample_db
    prices_db_path = tmp_path / "prices.db"
    db.init_db(db_path=str(prices_db_path))
    prices_conn = db.connect(db_path=str(prices_db_path))
    apply_migrations(prices_conn)

    # Copy sample data from sample_db to prices_db
    df_sample = pd.read_sql("SELECT * FROM prices WHERE ticker = 'PETR4'", sample_db)
    df_sample.to_sql("prices", prices_conn, if_exists="append", index=False)
    prices_conn.close()

    # Create separate metadata DB
    metadata_db_path = tmp_path / "metadata.db"
    db.init_db(db_path=str(metadata_db_path))
    metadata_conn = db.connect(db_path=str(metadata_db_path))
    apply_migrations(metadata_conn)
    metadata_conn.close()

    # Route price-read connections to our seeded prices DB by patching
    # both the public connector and the reference imported in prices.
    from src.db import connection

    def mock_prices_connect(db_path=None):
        return db.connect(db_path=str(prices_db_path))

    monkeypatch.setattr(connection, "connect", mock_prices_connect)
    monkeypatch.setattr(prices, "connect", mock_prices_connect)

    # Patch db.connect so that any metadata writes from the CLI go to
    # our test database.  We preserve the original function for other
    # calls (e.g. prices) and only redirect when the requested path matches
    # the metadata DB or is omitted.
    original_db_connect = db.connect

    def mock_db_connect(db_path=None, **kw):
        # if caller explicitly asked for our metadata DB, return that
        if db_path is None or str(db_path) == str(metadata_db_path):
            return original_db_connect(db_path=str(metadata_db_path))
        return original_db_connect(db_path=db_path, **kw)

    monkeypatch.setattr(db, "connect", mock_db_connect)

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result1 = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result1.exit_code == 0

    metadata_after_first = db.list_snapshots(
        ticker="PETR4", db_path=str(metadata_db_path)
    )
    assert len(metadata_after_first) == 1, "Expected 1 row after first run"
    first_job_id = metadata_after_first[0]["job_id"]

    result2 = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result2.exit_code == 0

    metadata_after_second = db.list_snapshots(
        ticker="PETR4", db_path=str(metadata_db_path)
    )
    assert len(metadata_after_second) == 1, (
        "Expected still 1 row after second run (idempotency via INSERT OR REPLACE)"
    )
    second_job_id = metadata_after_second[0]["job_id"]

    assert first_job_id == second_job_id, (
        f"job_id changed on rerun: {first_job_id} != {second_job_id}"
    )


def test_metadata_rows_count_matches_df(snapshot_test_db, tmp_path, monkeypatch):
    """rows field in DB matches len(df)."""

    db_path = snapshot_test_db

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0

    csv_path = output_dir / "PETR4_snapshot.csv"
    df = pd.read_csv(csv_path)
    actual_rows = len(df)

    metadata = db.list_snapshots(ticker="PETR4", db_path=str(db_path))
    assert len(metadata) >= 1
    recorded_rows = metadata[0]["rows"]

    assert recorded_rows == actual_rows, (
        f"DB rows field {recorded_rows} != actual CSV rows {actual_rows}"
    )


def test_metadata_size_bytes_matches_file(snapshot_test_db, tmp_path, monkeypatch):
    """size_bytes in DB matches file size of CSV."""

    db_path = snapshot_test_db

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0

    csv_path = output_dir / "PETR4_snapshot.csv"
    actual_size = csv_path.stat().st_size

    metadata = db.list_snapshots(ticker="PETR4", db_path=str(db_path))
    assert len(metadata) >= 1
    recorded_size = metadata[0]["size_bytes"]

    assert recorded_size == actual_size, (
        f"DB size_bytes {recorded_size} != file size {actual_size}"
    )
