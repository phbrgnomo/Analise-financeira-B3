import json
from pathlib import Path

from typer.testing import CliRunner

from src.main import app


def test_test_conn_dummy_provider_success():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "test-conn",
            "--provider",
            "dummy",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "success"
    assert "provider" in data
    assert data["provider"] == "dummy"
    assert "latency_ms" in data
    assert "last_success_at" in data


def test_test_conn_unknown_provider_fails():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "test-conn",
            "--provider",
            "__not_a_provider__",
            "--format",
            "json",
        ],
    )
    assert result.exit_code != 0
    data = json.loads(result.output)
    assert data["status"] == "failure"
    assert "error" in data


def test_health_command_reports_paths_and_metrics(tmp_path: Path, monkeypatch):
    # Create minimal filesystem structure for health checks
    db_file = tmp_path / "dados" / "data.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.write_text("sqlite")

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    ingest_log = tmp_path / "metadata" / "ingest_logs.jsonl"
    ingest_log.parent.mkdir(parents=True, exist_ok=True)
    ingest_log.write_text(
        json.dumps(
            {
                "job_id": "00000000-0000-0000-0000-000000000000",
                "status": "success",
                "created_at": "2026-01-01T00:00:00Z",
                "duration": "1.0s",
                "rows": 1,
                "provider": "dummy",
            }
        )
        + "\n"
    )

    # Force CLI to use our temp paths
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "health",
            "--format",
            "json",
            "--db-path",
            str(db_file),
            "--data-dir",
            str(tmp_path / "dados"),
            "--raw-dir",
            str(raw_dir),
            "--snapshots-dir",
            str(snapshots_dir),
            "--ingest-log-path",
            str(ingest_log),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] in {"ok", "warn", "error"}
    assert "paths" in data
    assert "metrics" in data
    assert "ingest_lag_seconds" in data["metrics"]["metrics"]
