import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app
from src.utils.checksums import sha256_file


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape sequences from CLI output."""

    import re

    ansi = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi.sub("", s)


@pytest.fixture
def isolated_cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate CLI artifacts and avoid writing to the repository DB.

    This fixture configures environment variables and overrides the default
    database path so tests can run without affecting the repo workspace.
    """

    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("LOCK_DIR", str(tmp_path / "locks"))

    from src.db import connection as conn_module

    monkeypatch.setattr(conn_module, "DEFAULT_DB_PATH", str(tmp_path / "data.db"))

    return tmp_path


def test_quickstart_no_network_generates_snapshot_and_checksum(
    isolated_cli_env, monkeypatch
):
    """Execute quickstart in --no-network mode and validate snapshot checksum."""

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--ticker", "PETR4", "--format", "json", "--no-network"],
    )

    assert result.exit_code == 0

    data = json.loads(_strip_ansi(result.output))
    assert data["status"] == "success"

    # Ensure the CLI reports snapshot metadata.
    tickers = data.get("tickers")
    ticker_info = tickers[0] if tickers and len(tickers) > 0 else {}
    snapshot_path = Path(ticker_info.get("snapshot_path", ""))
    checksum = ticker_info.get("snapshot_checksum")

    assert snapshot_path.exists(), "snapshot file should be written"
    assert checksum, "checksum should be reported in JSON output"

    checksum_path = snapshot_path.with_name(f"{snapshot_path.name}.checksum")
    assert checksum_path.exists(), "checksum sidecar should exist"

    assert sha256_file(snapshot_path) == checksum


def test_quickstart_no_network_cache_hit_json(isolated_cli_env, monkeypatch):
    """Cache hit should still include snapshot metadata in the JSON payload."""

    # Ensure dummy provider produces stable output across runs so caching can occur.
    from datetime import datetime, timezone

    import pandas as pd

    fixed_dates = pd.date_range(
        end=pd.Timestamp(datetime(2026, 1, 1, tzinfo=timezone.utc)),
        periods=3,
        freq="D",
        tz="UTC",
    )
    fixed_df = pd.DataFrame(
        {
            "Open": [1.0, 1.1, 1.2],
            "High": [1.1, 1.2, 1.3],
            "Low": [1.0, 1.05, 1.1],
            "Close": [1.0, 1.1, 1.2],
            "Adj Close": [1.0, 1.1, 1.2],
            "Volume": [100, 120, 110],
        },
        index=fixed_dates,
    )

    # Patch DummyAdapter so every run returns the same data
    monkeypatch.setattr(
        "src.adapters.dummy.DummyAdapter.fetch",
        lambda self, *args, **kwargs: fixed_df,
    )

    runner = CliRunner()
    ticker1 = _extracted_from_test_quickstart_no_network_cache_hit_json_34(runner)
    path1 = ticker1["snapshot_path"]
    checksum1 = ticker1["snapshot_checksum"]

    assert path1
    assert checksum1

    ticker2 = _extracted_from_test_quickstart_no_network_cache_hit_json_34(runner)
    assert ticker2["snapshot_path"] == path1
    assert ticker2["snapshot_checksum"] == checksum1


# TODO Rename this here and in `test_quickstart_no_network_cache_hit_json`
def _extracted_from_test_quickstart_no_network_cache_hit_json_34(runner):
    result1 = runner.invoke(
        app,
        ["--ticker", "PETR4", "--format", "json", "--no-network"],
    )
    assert result1.exit_code == 0
    data1 = json.loads(_strip_ansi(result1.output))

    return data1["tickers"][0]


def test_quickstart_no_network_run_notebook_json(
    isolated_cli_env, monkeypatch
):
    """Execute quickstart with --run-notebook and validate notebook summary."""

    tmp_path = isolated_cli_env

    def fake_run_notebook(tickers, job_id):
        return {
            "status": "success",
            "output_notebook": str(tmp_path / "reports" / f"quickstart-{job_id}.ipynb"),
        }

    monkeypatch.setattr("src.main._run_notebook", fake_run_notebook)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--ticker",
            "PETR4",
            "--format",
            "json",
            "--no-network",
            "--run-notebook",
        ],
    )

    assert result.exit_code == 0

    data = json.loads(_strip_ansi(result.output))
    assert data["status"] == "success"
    assert "notebook" in data
    assert isinstance(data["notebook"], dict)
    assert data["notebook"].get("status") == "success"
    assert data["notebook"].get("output_notebook", "").endswith(".ipynb")
