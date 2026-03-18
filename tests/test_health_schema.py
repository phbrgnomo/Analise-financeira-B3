import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import validate
from typer.testing import CliRunner

from src.main import app


def _write_sample_ingest_log(path: str) -> None:
    """Cria um ingest log fake para os testes de health."""
    now = datetime.now(timezone.utc)
    records = [
        {
            "job_id": "00000000-0000-0000-0000-000000000000",
            "source": "dummy",
            "status": "success",
            "finished_at": (now - timedelta(hours=1))
            .isoformat()
            .replace("+00:00", "Z"),
            "duration": "1.23s",
            "rows": 10,
        },
        {
            "job_id": "00000000-0000-0000-0000-000000000001",
            "source": "dummy",
            "status": "error",
            "finished_at": (now - timedelta(hours=2))
            .isoformat()
            .replace("+00:00", "Z"),
            "duration": "0.10s",
            "rows": 0,
        },
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_metrics_schema(tmp_path, monkeypatch):
    """Valida que a saída de `main metrics` segue o schema definido."""

    ingest_log = tmp_path / "ingest_logs.jsonl"
    _write_sample_ingest_log(str(ingest_log))

    # Force CLI to use our temp ingest logs file
    monkeypatch.setenv("INGEST_LOG_PATH", str(ingest_log))

    runner = CliRunner()
    result = runner.invoke(app, ["metrics", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)

    schema_path = (
        Path(__file__).resolve().parents[1] / "docs" / "schema" / "health_schema.json"
    )
    schema = json.load(schema_path.open("r", encoding="utf-8"))

    validate(instance=data, schema=schema)
