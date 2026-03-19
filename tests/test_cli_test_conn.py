import json

from typer.testing import CliRunner

from src.main import app


def test_conn_dummy_provider_success():
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
    assert data["provider"] == "dummy"
    assert "latency_ms" in data
    assert "last_success_at" in data


def test_conn_unknown_provider_failure():
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
