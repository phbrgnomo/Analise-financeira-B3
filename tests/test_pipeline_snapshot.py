"""Tests for `pipeline snapshot` CLI command (Story 2-1).

Verifies all behaviors of the snapshot generation command:
- CSV file creation in output directory
- Correct CSV columns matching read_prices() output
- Date range filtering (--start and --end)
- Exit code 1 for invalid ticker
- Exit code 1 for empty date range
- Output directory creation when missing
- Default output directory behavior (SNAPSHOTS_DIR)
"""

import re
from typing import Pattern

import pandas as pd
from typer.testing import CliRunner

from src.main import app


def _strip_ansi(s: str) -> str:
    """Remove ANSI/escape sequences for format-independent assertions."""
    ansi: Pattern[str] = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi.sub("", s)


def test_snapshot_generates_csv_file(sample_db, tmp_path, monkeypatch):
    """Valid ticker generates CSV file in output directory."""
    from src import db

    monkeypatch.setattr(db, "connect", lambda **kw: sample_db)

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
    csv_path = output_dir / "PETR4_snapshot.csv"
    assert csv_path.exists(), f"Expected snapshot file not created: {csv_path}"
    assert csv_path.stat().st_size > 0, "Snapshot file is empty"


def test_snapshot_csv_has_correct_columns(sample_db, tmp_path, monkeypatch):
    """CSV columns match read_prices() output (canonical schema).

    Snapshot includes all DB columns sorted alphabetically by serialize_df_bytes.
    """
    from src import db

    monkeypatch.setattr(db, "connect", lambda **kw: sample_db)

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

    expected_core = {"close", "date", "high", "low", "open", "ticker", "volume"}
    actual_cols = set(df.columns)
    missing = expected_core - actual_cols
    assert not missing, (
        f"Missing required columns in snapshot: "
        f"{sorted(missing)}. Got: {sorted(actual_cols)}"
    )


def test_snapshot_with_date_range(sample_db, tmp_path, monkeypatch):
    """--start and --end filter data correctly."""
    from src import db
    from src.db import prices
    # the date-range command path performs low-level price reads via
    # ``prices._connect``; patching only ``db.connect`` does not intercept
    # those calls, so we patch both helpers here.
    monkeypatch.setattr(prices, "_connect", lambda db_path=None: sample_db)
    monkeypatch.setattr(db, "connect", lambda **kw: sample_db)

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--start",
            "2023-01-03",
            "--end",
            "2023-01-04",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, (
        f"CLI failed with exit code {result.exit_code}. Output: {result.output}"
    )
    csv_path = output_dir / "PETR4_snapshot.csv"
    assert csv_path.exists(), f"Snapshot file not created: {csv_path}"
    df = pd.read_csv(csv_path)

    assert len(df) == 2, (
        f"Expected 2 rows in filtered range [2023-01-03, 2023-01-04], "
        f"got {len(df)}"
    )
    dates = df["date"].tolist()
    assert "2023-01-03" in dates
    assert "2023-01-04" in dates


def test_snapshot_invalid_ticker_exit_code_1(sample_db, tmp_path, monkeypatch):
    """Unknown ticker produces exit code 1."""
    # ensure CLI uses the sample database instead of real data
    from src import db

    monkeypatch.setattr(db, "connect", lambda **kw: sample_db)

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "INVALID99",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 1, "Expected exit code 1 for invalid ticker"
    plain_output = _strip_ansi(result.output).lower()
    assert (
        "ticker inválido" in plain_output or "nenhum dado encontrado" in plain_output
    )


def test_snapshot_empty_date_range_exit_code_1(sample_db, tmp_path, monkeypatch):
    """Valid ticker but no data in date range produces exit code 1."""
    from src import db

    monkeypatch.setattr(db, "connect", lambda **kw: sample_db)

    runner = CliRunner()
    output_dir = tmp_path / "snapshots"

    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
            "--start",
            "2020-01-01",
            "--end",
            "2020-01-31",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 1, "Expected exit code 1 for empty date range"
    plain_output = _strip_ansi(result.output).lower()
    assert "nenhum dado encontrado" in plain_output


def test_snapshot_creates_output_dir(sample_db, tmp_path, monkeypatch):
    """Non-existent output directory is created automatically."""
    from src import db

    monkeypatch.setattr(db, "connect", lambda **kw: sample_db)

    runner = CliRunner()
    output_dir = tmp_path / "does_not_exist" / "nested" / "snapshots"

    assert not output_dir.exists()

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
    assert output_dir.exists(), "Output directory should be created"
    assert output_dir.is_dir(), "Output path should be a directory"
    csv_path = output_dir / "PETR4_snapshot.csv"
    assert csv_path.exists(), "Snapshot file should be created in new directory"


def test_snapshot_default_output_dir(sample_db, tmp_path, monkeypatch):
    """Without --output-dir, command uses SNAPSHOTS_DIR.

    Monkeypatch SNAPSHOTS_DIR in pipeline module since it's imported there.
    """
    from src import db, pipeline

    monkeypatch.setattr(db, "connect", lambda **kw: sample_db)
    test_snapshots_dir = tmp_path / "snapshots"
    monkeypatch.setattr(pipeline, "SNAPSHOTS_DIR", test_snapshots_dir)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "pipeline",
            "snapshot",
            "--ticker",
            "PETR4",
        ],
    )

    assert result.exit_code == 0
    csv_path = test_snapshots_dir / "PETR4_snapshot.csv"
    assert csv_path.exists(), (
        f"Snapshot should be created in default SNAPSHOTS_DIR: {csv_path}"
    )
