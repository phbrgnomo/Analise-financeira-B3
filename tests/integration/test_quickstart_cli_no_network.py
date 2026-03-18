import json
from pathlib import Path

from typer.testing import CliRunner

from src.main import app
from src.utils.checksums import sha256_file


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape sequences from CLI output."""

    import re

    ansi = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi.sub("", s)


def test_quickstart_no_network_generates_snapshot_and_checksum(tmp_path, monkeypatch):
    """Execute quickstart in --no-network mode and validate snapshot checksum."""

    # Keep artifacts isolated from the repository workspace.
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("LOCK_DIR", str(tmp_path / "locks"))

    # Prevent writing to the repo-local DB.
    from src.db import connection as conn_module

    monkeypatch.setattr(conn_module, "DEFAULT_DB_PATH", str(tmp_path / "data.db"))

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--ticker", "PETR4", "--format", "json", "--no-network"],
    )

    assert result.exit_code == 0

    data = json.loads(_strip_ansi(result.output))
    assert data["status"] == "success"

    # Ensure the CLI reports snapshot metadata.
    ticker_info = data.get("tickers", [{}])[0]
    snapshot_path = Path(ticker_info.get("snapshot_path", ""))
    checksum = ticker_info.get("snapshot_checksum")

    assert snapshot_path.exists(), "snapshot file should be written"
    assert checksum, "checksum should be reported in JSON output"

    checksum_path = snapshot_path.with_name(f"{snapshot_path.name}.checksum")
    assert checksum_path.exists(), "checksum sidecar should exist"

    assert sha256_file(snapshot_path) == checksum


def test_quickstart_no_network_run_notebook_json(tmp_path, monkeypatch):
    """Execute quickstart with --run-notebook and validate notebook summary."""

    # Keep artifacts isolated from the repository workspace.
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("LOCK_DIR", str(tmp_path / "locks"))

    # Prevent writing to the repo-local DB.
    from src.db import connection as conn_module

    monkeypatch.setattr(conn_module, "DEFAULT_DB_PATH", str(tmp_path / "data.db"))

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
