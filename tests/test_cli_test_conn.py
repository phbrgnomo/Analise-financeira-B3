import json

from typer.testing import CliRunner

from src import connectivity
from src.main import app


def test_conn_dummy_provider_success(monkeypatch, tmp_path):
    """Runs `test-conn --provider dummy --format json` and validates last_success_at.

    last_success_at is computed from the ingest log; we ensure that the most recent
    successful dummy entry is selected, and that no-success logs yield `null`.
    """

    runner = CliRunner()

    # Build an ingest log containing mixed providers and statuses.
    ingest_log = tmp_path / "ingest_logs.jsonl"
    entries = [
        {
            "provider": "dummy",
            "status": "failure",
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "provider": "dummy",
            "status": "success",
            "created_at": "2024-01-02T12:00:00Z",
        },
        {
            "provider": "other",
            "status": "success",
            "created_at": "2024-01-03T00:00:00Z",
        },
        {
            "provider": "dummy",
            "status": "success",
            "created_at": "2024-01-03T15:30:00Z",
        },
    ]
    data = _extracted_from_test_conn_dummy_provider_success_(
        ingest_log, entries, monkeypatch, runner
    )
    expected_last_success_at = "2024-01-03T15:30:00Z"
    assert data["last_success_at"] == expected_last_success_at

    # Verify the behavior when there are no successful dummy entries.
    ingest_log_no_success = tmp_path / "ingest_logs_no_success.jsonl"
    entries_no_success = [
        {
            "provider": "dummy",
            "status": "failure",
            "created_at": "2024-02-01T00:00:00Z",
        },
        {
            "provider": "other",
            "status": "success",
            "created_at": "2024-02-02T00:00:00Z",
        },
    ]
    data_no_success = _extracted_from_test_conn_dummy_provider_success_(
        ingest_log_no_success, entries_no_success, monkeypatch, runner
    )
    assert data_no_success["last_success_at"] is None


# TODO Rename this here and in `test_conn_dummy_provider_success`
def _extracted_from_test_conn_dummy_provider_success_(arg0, arg1, monkeypatch, runner):
    arg0.write_text("\n".join(json.dumps(e) for e in arg1) + "\n")

    monkeypatch.setenv("INGEST_LOG_PATH", str(arg0))

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
    result = json.loads(result.output)
    assert result["status"] == "success"
    assert result["provider"] == "dummy"
    assert "latency_ms" in result
    return result


def test_conn_timeout_passed_to_adapter(monkeypatch, tmp_path):
    """Verify --timeout is forwarded to the adapter's check_connection()."""

    received: dict[str, float | None] = {}

    class DummyAdapter:
        def check_connection(self, timeout=None):
            received["timeout"] = timeout
            return {"status": "success", "error": None, "latency_ms": 123.0}

    monkeypatch.setattr(connectivity, "get_adapter", lambda provider: DummyAdapter())

    # Ensure get_last_success_timestamp returns None consistently.
    ingest_log = tmp_path / "ingest_logs.jsonl"
    ingest_log.write_text("")
    monkeypatch.setenv("INGEST_LOG_PATH", str(ingest_log))

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "test-conn",
            "--provider",
            "dummy",
            "--timeout",
            "1.5",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert received["timeout"] == 1.5

    data = json.loads(result.output)
    assert data["status"] == "success"
    assert data["provider"] == "dummy"
    assert data["latency_ms"] == 123.0
    assert data["last_success_at"] is None


def test_conn_failure_writes_ingest_log(monkeypatch, tmp_path):
    """Verify failure paths log an ingest entry via append_ingest_log_entry."""

    runner = CliRunner()
    ingest_log_path = tmp_path / "ingest.log"

    monkeypatch.setenv("INGEST_LOG_PATH", str(ingest_log_path))

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
    cli_data = json.loads(result.output)
    assert cli_data["status"] == "failure"
    assert "error" in cli_data
    assert cli_data["error"]

    assert ingest_log_path.exists()
    log_lines = ingest_log_path.read_text().splitlines()
    assert log_lines, "Expected at least one ingest log line for failed test-conn"

    last_entry = json.loads(log_lines[-1])
    assert last_entry.get("status") != "success"
    assert last_entry.get("provider") == "__not_a_provider__"
    assert last_entry.get("error")
    assert isinstance(last_entry["error"], str)


def test_conn_unknown_provider_failure():
    """Verifies the CLI returns JSON failure output when a provider is unknown."""

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

    try:
        data = json.loads(result.output)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Expected JSON output but received invalid JSON:\n{result.output}"
        ) from e

    assert data["status"] == "failure"
    assert "error" in data
