import json
from pathlib import Path

from jsonschema import validate
from typer.testing import CliRunner

import src.ingest.raw_storage as raw_storage
from src.main import app


def test_cli_json_schema(tmp_path, monkeypatch):
    """Verifica que a saída JSON de `main --format json` segue o schema."""

    # Ensure a clean, isolated data directory so caching/database state from
    # other tests doesn't affect this validation scenario.
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("SNAPSHOT_CACHE_FILE", str(tmp_path / "snapshot_cache.json"))
    monkeypatch.setenv("LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(raw_storage, "DEFAULT_DB", tmp_path / "data.db")

    runner = CliRunner()
    result = runner.invoke(
        app, ["--ticker", "PETR4", "--format", "json", "--no-network"]
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = json.loads(result.output)

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "schema"
        / "cli_summary_schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    validate(instance=data, schema=schema)
