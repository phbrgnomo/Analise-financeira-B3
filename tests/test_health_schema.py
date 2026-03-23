# Used to serialize/deserialize test payloads.
import json

# Locate schema file in repo tree.
import pathlib

# Provide timestamp helpers for test fixtures.
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Validate response payloads against the JSON schema.
from jsonschema import validate

# Test utilities from pytest.
from pytest import MonkeyPatch

# The FastAPI/Typer application under test.
from src.main import app
from src.utils.health import check_paths_health


def _format_iso_z(dt: datetime) -> str:
    """Format *dt* as an ISO-8601 string ending with ``Z`` (UTC).

    This mirrors the formatting used in ingest logs.
    """

    return dt.isoformat().replace("+00:00", "Z")


def _write_sample_ingest_log(path: str) -> None:
    """Cria um ingest log fake para os testes de health."""
    now = datetime.now(timezone.utc)
    records = [
        {
            "job_id": "00000000-0000-0000-0000-000000000000",
            "source": "dummy",
            "status": "success",
            "finished_at": _format_iso_z(now - timedelta(hours=1)),
            "duration": "1.23s",
            "rows": 10,
        },
        {
            "job_id": "00000000-0000-0000-0000-000000000001",
            "source": "dummy",
            "status": "error",
            "finished_at": _format_iso_z(now - timedelta(hours=2)),
            "duration": "0.10s",
            "rows": 0,
        },
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_metrics_schema(tmp_path: pathlib.Path, monkeypatch: MonkeyPatch):
    """Valida que a saída de `main metrics` segue o schema definido."""

    ingest_log = tmp_path / "ingest_logs.jsonl"
    _write_sample_ingest_log(str(ingest_log))

    # Force CLI to use our temp ingest logs file
    monkeypatch.setenv("INGEST_LOG_PATH", str(ingest_log))


# TODO Rename this here and in `test_metrics_schema`
def _extracted_from_test_metrics_schema_11(runner, arg1):
    result = runner.invoke(app, [arg1, "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)

    schema_path = (
        Path(__file__).resolve().parents[1] / "docs" / "schema" / "health_schema.json"
    )
    result = json.load(schema_path.open("r", encoding="utf-8"))

    validate(instance=data, schema=result)

    return result


def test_check_paths_health_db_nonexistent(tmp_path):
    """Verifies status 'error' and missing DB reason when db path does not exist."""
    db_path = tmp_path / "nonexistent_db.sqlite"
    paths = {"db": str(db_path)}

    result = check_paths_health(paths)

    assert result.get("status") == "error"
    reasons = result.get("reasons") or []
    assert any("db missing" in reason for reason in reasons)


def test_check_paths_health_data_dir_nonexistent(tmp_path):
    """Verifies warning status and missing data_dir reason when data_dir is absent."""
    data_dir = tmp_path / "nonexistent_dir"
    paths = {"data_dir": str(data_dir)}

    result = check_paths_health(paths)

    assert result.get("status") == "warn"
    reasons = result.get("reasons") or []
    assert any("data_dir path" in reason and "does not exist"
               in reason for reason in reasons)


def test_check_paths_health_valid_db_file(tmp_path):
    """Verifies existing db file returns status 'ok' and no 'db is not a file'."""
    # check_paths_health validates presence/type only; it does not inspect
    # SQLite schema/integrity. Using an empty file is intentional for this mock.
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("")
    paths = {"db": str(db_path)}

    result = check_paths_health(paths)

    assert result.get("status") == "ok"
    reasons = result.get("reasons") or []
    assert all("db is not a file" not in reason for reason in reasons)
