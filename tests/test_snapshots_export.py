"""Tests for `snapshots export` CLI command (Story 2-3).

Verifies all behaviors of the snapshot export command:
- CSV export to stdout with stderr status messages
- JSON export with metadata wrapper and records orientation
- File output via --output flag (CSV and JSON)
- Exit code 1 for unknown ticker
- JSON metadata fields validation
- CLI mounting in main app
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from src import db
from src.db.snapshots import record_snapshot_metadata
from src.etl.snapshot import write_snapshot
from src.main import app


def _setup_snapshot(ticker: str, tmp_path: Path, conn) -> tuple[Path, str]:
    """Create a test snapshot and register metadata.

    Returns:
        Tuple of (snapshot_path, checksum)
    """
    from datetime import UTC, datetime

    import pandas as pd

    # Initialize DB schema
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
            archived_at TEXT
        )
        """
    )
    conn.commit()

    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "open": [10.0, 11.0, 12.0],
            "high": [10.5, 11.5, 12.5],
            "low": [9.5, 10.5, 11.5],
            "close": [10.2, 11.2, 12.2],
            "adj_close": [10.2, 11.2, 12.2],
            "volume": [1000, 1100, 1200],
        }
    )

    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_filename = f"{ticker}-{timestamp}.csv"
    snapshot_path = snapshot_dir / snapshot_filename

    checksum = write_snapshot(df, snapshot_path)

    checksum_file = snapshot_path.with_suffix(".csv.checksum")
    checksum_file.write_text(checksum)

    metadata = {
        "ticker": ticker,
        "snapshot_path": str(snapshot_path),
        "checksum": checksum,
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "rows": len(df),
    }
    record_snapshot_metadata(metadata=metadata, conn=conn)

    return snapshot_path, checksum


def test_export_csv_to_stdout(tmp_path, monkeypatch):
    """CSV data on stdout, status messages on stderr."""
    test_db_path = str(tmp_path / "test.db")
    conn = db.connect(db_path=test_db_path)

    # Patch _connect at all import locations
    from src.db import connection, snapshots
    monkeypatch.setattr(connection, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(db, "connect", lambda **kw: conn)

    try:
        snapshot_path, _ = _setup_snapshot("PETR4", tmp_path, conn)

        from src import snapshot_cli

        monkeypatch.setattr(snapshot_cli, "SNAPSHOTS_DIR", tmp_path / "snapshots")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["snapshots", "export", "--ticker", "PETR4", "--format", "csv"],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        csv_lines = result.stdout.strip().split("\n")
        header = csv_lines[0]
        assert "date" in header and "open" in header and "close" in header
        assert "adj_close" in header and "volume" in header
        assert "2024-01-01" in result.stdout
        assert "10," in result.stdout or "10.0" in result.stdout

        assert "Exporting snapshot" in result.output
    finally:
        conn.close()


def test_export_json_to_stdout(tmp_path, monkeypatch):
    """JSON export with metadata wrapper and records orientation."""
    test_db_path = str(tmp_path / "test.db")
    conn = db.connect(db_path=test_db_path)

    # Patch _connect at all import locations
    from src.db import connection, snapshots
    monkeypatch.setattr(connection, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(db, "connect", lambda **kw: conn)

    try:
        snapshot_path, checksum = _setup_snapshot("PETR4", tmp_path, conn)

        from src import snapshot_cli

        monkeypatch.setattr(snapshot_cli, "SNAPSHOTS_DIR", tmp_path / "snapshots")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["snapshots", "export", "--ticker", "PETR4", "--format", "json"],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        data = json.loads(result.stdout)

        assert "ticker" in data
        assert data["ticker"] == "PETR4"
        assert "checksum" in data
        assert "rows" in data
        assert data["rows"] == 3
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 3
    finally:
        conn.close()


def test_export_csv_to_file(tmp_path, monkeypatch):
    """--output flag writes CSV file correctly."""
    test_db_path = str(tmp_path / "test.db")
    conn = db.connect(db_path=test_db_path)

    # Patch _connect at all import locations
    from src.db import connection, snapshots
    monkeypatch.setattr(connection, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(db, "connect", lambda **kw: conn)

    try:
        snapshot_path, _ = _setup_snapshot("PETR4", tmp_path, conn)

        from src import snapshot_cli

        monkeypatch.setattr(snapshot_cli, "SNAPSHOTS_DIR", tmp_path / "snapshots")

        output_file = tmp_path / "export.csv"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "snapshots",
                "export",
                "--ticker",
                "PETR4",
                "--format",
                "csv",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert output_file.exists(), "Output file not created"

        content = output_file.read_text()
        csv_lines = content.strip().split("\n")
        header = csv_lines[0]
        assert "date" in header and "open" in header and "close" in header
        assert "adj_close" in header and "volume" in header
        assert "2024-01-01" in content
    finally:
        conn.close()


def test_export_json_to_file(tmp_path, monkeypatch):
    """--output flag writes JSON file correctly."""
    test_db_path = str(tmp_path / "test.db")
    conn = db.connect(db_path=test_db_path)

    # Patch _connect at all import locations
    from src.db import connection, snapshots
    monkeypatch.setattr(connection, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(db, "connect", lambda **kw: conn)

    try:
        snapshot_path, _ = _setup_snapshot("PETR4", tmp_path, conn)

        from src import snapshot_cli

        monkeypatch.setattr(snapshot_cli, "SNAPSHOTS_DIR", tmp_path / "snapshots")

        output_file = tmp_path / "export.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "snapshots",
                "export",
                "--ticker",
                "PETR4",
                "--format",
                "json",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert output_file.exists(), "Output file not created"

        data = json.loads(output_file.read_text())
        assert data["ticker"] == "PETR4"
        assert data["rows"] == 3
    finally:
        conn.close()


def test_export_no_snapshot_exit_1(tmp_path, monkeypatch):
    """Unknown ticker produces exit code 1 with error message."""
    conn = db.connect(db_path=str(tmp_path / "test.db"))
    try:
        from src import snapshot_cli

        monkeypatch.setattr(snapshot_cli, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(db, "connect", lambda **kw: conn)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "snapshots",
                "export",
                "--ticker",
                "INVALID99",
                "--format",
                "csv",
            ],
        )

        assert result.exit_code == 1, "Expected exit code 1 for unknown ticker"
        assert "No snapshots found" in result.output
    finally:
        conn.close()


def test_export_json_has_metadata_fields(tmp_path, monkeypatch):
    """JSON contains ticker, checksum, rows, data."""
    test_db_path = str(tmp_path / "test.db")
    conn = db.connect(db_path=test_db_path)

    # Patch _connect at all import locations
    from src.db import connection, snapshots
    monkeypatch.setattr(connection, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: conn)
    monkeypatch.setattr(db, "connect", lambda **kw: conn)

    try:
        snapshot_path, checksum = _setup_snapshot("PETR4", tmp_path, conn)

        from src import snapshot_cli

        monkeypatch.setattr(snapshot_cli, "SNAPSHOTS_DIR", tmp_path / "snapshots")

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["snapshots", "export", "--ticker", "PETR4", "--format", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)

        required_fields = ["ticker", "checksum", "rows", "data"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        assert isinstance(data["ticker"], str)
        assert isinstance(data["rows"], int)
        assert isinstance(data["data"], list)
    finally:
        conn.close()


def test_snapshots_subapp_mounted(tmp_path, monkeypatch):
    """snapshots export --help works from main app."""
    runner = CliRunner()
    result = runner.invoke(app, ["snapshots", "export", "--help"])

    assert result.exit_code == 0, f"Help command failed: {result.stdout}"
    assert "export" in result.stdout.lower()
    assert "--ticker" in result.stdout
    assert "--format" in result.stdout
