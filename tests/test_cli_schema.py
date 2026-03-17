import json
from pathlib import Path

from jsonschema import validate
from typer.testing import CliRunner

from src.main import app


def test_cli_json_schema():
    """Verifica que a saída JSON de `main --format json` segue o schema."""
    runner = CliRunner()
    result = runner.invoke(
        app, ["--ticker", "PETR4", "--format", "json", "--no-network"]
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = json.loads(result.output)

    schema_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "docs"
        / "schema"
        / "cli_summary_schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    validate(instance=data, schema=schema)
