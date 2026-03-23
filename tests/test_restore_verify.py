"""Tests for `pipeline restore-verify` CLI command (Story 2-6).

Verifies all behaviors of the snapshot restore-verify command:
- Exit code 0 (PASS) when all checks pass
- Exit code 1 (WARN) when checksum mismatches but structure valid
- Exit code 2 (FAIL) when file missing or invalid CSV or columns missing
- JSON report structure validation (job_id, snapshot_path, timestamp,
  checks, rows_restored, overall_result)
- All 4 integrity checks individually (row_count, columns_present,
  checksum_match, sample_row_check)
- Edge cases: missing file, corrupted data, missing metadata
"""

# ruff: noqa: I001

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

from src import db
from src.main import app
from src.db.snapshots import _normalize_snapshot_path
from src.utils.checksums import sha256_file


@pytest.fixture
def patch_db_connect(monkeypatch, mock_metadata_db):
    """Patch `src.db.connect` to always use the test metadata DB.

    This allows CLI commands under test to use the in-memory metadata DB
    prepared by the `mock_metadata_db` fixture without having to patch
    `db.connect` repeatedly in each test.
    """

    _, metadata_db_path = mock_metadata_db
    original_connect = db.connect

    def mock_db_connect(db_path=None, **kw):
        return original_connect(db_path=str(metadata_db_path), **kw)

    monkeypatch.setattr(db, "connect", mock_db_connect)
    return metadata_db_path


def _extract_json_from_cli_output(output: str) -> dict[str, Any]:
    """Extract JSON report from CLI output containing status messages.

    The restore-verify CLI outputs status messages mixed with JSON:
        ▶ pipeline restore-verify: iniciando verificação de restauração
        • {
          "job_id": "...",
          ...
        }
        ✓ Verificação concluída com sucesso

    This helper extracts the JSON block from the mixed output.

    Args:
        output: CLI stdout containing status messages and JSON

    Returns:
        Parsed JSON report as dict
    """
    if json_match := re.search(r"\{.*\}", output, re.DOTALL):
        return json.loads(json_match.group())
    else:
        raise ValueError(f"No JSON found in CLI output:\n{output}")


def _create_test_snapshot_with_metadata(
    ticker: str,
    tmp_path: Path,
    conn,
    tamper_file: bool = False,
) -> tuple[Path, str]:
    """Create test snapshot CSV and register metadata in DB.

    Args:
        ticker: Ticker symbol (e.g., PETR4)
        tmp_path: pytest tmp_path fixture
        conn: Database connection
        tamper_file: If True, modify file after metadata creation

    Returns:
        Tuple of (snapshot_path, checksum)
    """
    # Create snapshot CSV
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_filename = f"{ticker}-{timestamp}.csv"
    snapshot_path = snapshot_dir / snapshot_filename

    # Write CSV with all required columns
    df = pd.DataFrame(
        {
            "ticker": [ticker] * 3,
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "open": [10.0, 11.0, 12.0],
            "high": [10.5, 11.5, 12.5],
            "low": [9.5, 10.5, 11.5],
            "close": [10.2, 11.2, 12.2],
            "volume": [1000, 1100, 1200],
            "adj_close": [10.2, 11.2, 12.2],
        }
    )
    df.to_csv(snapshot_path, index=False)

    # Compute checksum
    checksum = sha256_file(snapshot_path)

    # Register metadata in DB
    from unittest.mock import patch

    # Ensure normalization retains an absolute path in the test environment
    # (pytest tmp_path typically lives under the system temp dir).
    with patch("tempfile.gettempdir", return_value="/nonexistent-tempdir"):
        normalized_path = _normalize_snapshot_path(str(snapshot_path))

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO snapshots (
            id, ticker, snapshot_path, checksum, rows,
            size_bytes, created_at, archived
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"{ticker}-{timestamp}",
            ticker,
            normalized_path,
            checksum,
            len(df),
            snapshot_path.stat().st_size,
            datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            0,
        ),
    )
    conn.commit()

    if tamper_file:
        tampered_df = df.copy()
        tampered_df.loc[0, "close"] = 999.99
        tampered_df.to_csv(snapshot_path, index=False)

    return snapshot_path, checksum


def test_restore_verify_pass(mock_metadata_db, tmp_path):
    """Valid snapshot with all checks passing → exit 0, overall_result=PASS."""
    metadata_conn, metadata_db_path = mock_metadata_db

    # Create snapshot with metadata
    snapshot_path, _ = _create_test_snapshot_with_metadata(
        "PETR4", tmp_path, metadata_conn
    )
    metadata_conn.close()

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(snapshot_path)],
    )

    # Verify exit code 0
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    report = _extract_json_from_cli_output(result.stdout)

    assert "job_id" in report
    assert "snapshot_path" in report
    assert "timestamp" in report
    assert "checks" in report
    assert "rows_restored" in report
    assert "overall_result" in report

    # Verify overall result
    assert report["overall_result"] == "PASS"
    assert report["rows_restored"] == 3

    # Verify all checks passed
    checks = report["checks"]
    assert checks["row_count"] == "pass"
    assert checks["columns_present"] == "pass"
    assert checks["checksum_match"] == "pass"
    assert checks["sample_row_check"] == "pass"

    # Verify status message in stderr
    assert "sucesso" in result.output.lower()


def test_restore_verify_missing_file(mock_metadata_db, tmp_path):
    """Non-existent snapshot file → exit 2, overall_result=FAIL."""
    _, metadata_db_path = mock_metadata_db

    # Run restore-verify with non-existent path
    missing_path = tmp_path / "does_not_exist.csv"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(missing_path)],
    )

    # Verify exit code 2
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"

    # Verify error message
    assert "not found" in result.output.lower()


def test_restore_verify_checksum_mismatch(mock_metadata_db, tmp_path):
    """Valid structure but tampered file → exit 1, overall_result=WARN."""
    metadata_conn, metadata_db_path = mock_metadata_db

    # Create snapshot with metadata, then tamper file
    snapshot_path, _ = _create_test_snapshot_with_metadata(
        "PETR4", tmp_path, metadata_conn, tamper_file=True
    )
    metadata_conn.close()

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(snapshot_path)],
    )

    assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}"

    report = _extract_json_from_cli_output(result.stdout)
    assert report["overall_result"] == "WARN"

    # Verify checksum check failed
    checks = report["checks"]
    assert checks["checksum_match"] == "fail"

    # Verify warning message in stderr
    assert "alerta" in result.output.lower() or "warn" in result.output.lower()


def test_restore_verify_invalid_csv(mock_metadata_db, tmp_path):
    """Malformed CSV file → exit 2, overall_result=FAIL."""
    _, metadata_db_path = mock_metadata_db

    # Create invalid CSV
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    invalid_csv = snapshot_dir / "invalid.csv"
    invalid_csv.write_text('col1,col2\n"value_without_end\n')

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(invalid_csv)],
    )

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"

    report = _extract_json_from_cli_output(result.stdout)
    assert report["overall_result"] == "FAIL"


def test_restore_verify_missing_metadata(mock_metadata_db, patch_db_connect, tmp_path):
    """Snapshot file exists but no metadata in DB → n/a checksum,
    but structure validated.
    """
    metadata_conn, metadata_db_path = mock_metadata_db
    metadata_conn.close()

    # Create snapshot CSV without metadata
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot_path = snapshot_dir / "PETR4-20240101T000000Z.csv"

    df = pd.DataFrame(
        {
            "ticker": ["PETR4"] * 3,
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "open": [10.0, 11.0, 12.0],
            "high": [10.5, 11.5, 12.5],
            "low": [9.5, 10.5, 11.5],
            "close": [10.2, 11.2, 12.2],
            "volume": [1000, 1100, 1200],
            "adj_close": [10.2, 11.2, 12.2],
        }
    )
    df.to_csv(snapshot_path, index=False)

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(snapshot_path)],
    )

    assert result.exit_code == 2, f"CLI failed: {result.output}"

    report = _extract_json_from_cli_output(result.stdout)
    assert report["overall_result"] == "FAIL"

    # Missing metadata should be treated as a failure
    checks = report["checks"]
    assert checks["checksum_match"] == "fail"


def test_restore_verify_json_report_structure(
    mock_metadata_db, patch_db_connect, tmp_path
):
    """Validate JSON report has all required keys with correct types."""
    metadata_conn, metadata_db_path = mock_metadata_db

    # Create snapshot with metadata
    snapshot_path, _ = _create_test_snapshot_with_metadata(
        "PETR4", tmp_path, metadata_conn
    )
    metadata_conn.close()

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(snapshot_path)],
    )

    assert result.exit_code == 0

    report = _extract_json_from_cli_output(result.stdout)

    # Validate required keys exist
    required_keys = {
        "job_id",
        "snapshot_path",
        "timestamp",
        "checks",
        "rows_restored",
        "overall_result",
    }
    missing = required_keys - report.keys()
    assert not missing, f"Missing required keys: {sorted(missing)}"

    # Validate types
    assert isinstance(report["job_id"], str)
    assert isinstance(report["snapshot_path"], str)
    assert isinstance(report["timestamp"], str)
    assert isinstance(report["checks"], dict)
    assert isinstance(report["rows_restored"], int)
    assert isinstance(report["overall_result"], str)

    # Validate checks dict structure
    checks = report["checks"]
    required_checks = {
        "row_count",
        "columns_present",
        "checksum_match",
        "sample_row_check",
    }
    missing_checks = required_checks - checks.keys()
    assert not missing_checks, f"Missing check(s): {sorted(missing_checks)}"
    # all recorded values must be one of the accepted statuses
    assert set(checks.values()) <= {"pass", "fail", "n/a"}


def test_restore_verify_missing_columns(mock_metadata_db, patch_db_connect, tmp_path):
    """CSV missing required columns → exit 2, columns_present=fail."""
    # Create CSV missing required columns (no 'close' column)
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot_path = snapshot_dir / "PETR4-20240101T000000Z.csv"

    df = pd.DataFrame(
        {
            "ticker": ["PETR4"] * 3,
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "open": [10.0, 11.0, 12.0],
            "high": [10.5, 11.5, 12.5],
            "low": [9.5, 10.5, 11.5],
            # Missing 'close', 'volume', 'adj_close'
        }
    )
    df.to_csv(snapshot_path, index=False)

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(snapshot_path)],
    )

    # Verify exit code 2 (FAIL)
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}"

    report = _extract_json_from_cli_output(result.stdout)
    assert report["overall_result"] == "FAIL"
    assert report["checks"]["columns_present"] == "fail"


def test_restore_verify_row_count_check(mock_metadata_db, patch_db_connect, tmp_path):
    """Verify row_count integrity check logic."""
    metadata_conn, _ = mock_metadata_db

    # Create snapshot with known row count
    snapshot_path, _ = _create_test_snapshot_with_metadata(
        "PETR4", tmp_path, metadata_conn
    )
    metadata_conn.close()

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(snapshot_path)],
    )

    assert result.exit_code == 0

    report = _extract_json_from_cli_output(result.stdout)

    # Verify row count matches
    assert report["rows_restored"] == 3
    assert report["checks"]["row_count"] == "pass"


def test_restore_verify_sample_row_check(mock_metadata_db, patch_db_connect, tmp_path):
    """Verify sample_row_check validates first and last rows exist in DB."""
    metadata_conn, _ = mock_metadata_db

    # Create snapshot with metadata
    snapshot_path, _ = _create_test_snapshot_with_metadata(
        "PETR4", tmp_path, metadata_conn
    )
    metadata_conn.close()

    # Run restore-verify
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["pipeline", "restore-verify", "--snapshot-path", str(snapshot_path)],
    )

    assert result.exit_code == 0

    report = _extract_json_from_cli_output(result.stdout)

    # Verify sample_row_check passed
    assert report["checks"]["sample_row_check"] == "pass"


def test_restore_verify_help():
    """--help flag works correctly."""
    runner = CliRunner()
    result = runner.invoke(app, ["pipeline", "restore-verify", "--help"])

    assert result.exit_code == 0
    # remove ANSI color codes which can interfere with substring checks
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "restore-verify" in clean
    # some environments (CI) may render dashes differently; check keyword only
    assert "snapshot-path" in clean
    assert "temp-db" in clean
