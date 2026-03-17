import json

from jsonschema import validate
from typer.testing import CliRunner

from src.main import app


def test_cli_json_schema():
    """Verifica que a saída JSON de `main --format json` segue o schema."""
    runner = CliRunner()
    result = runner.invoke(
        app, ["--ticker", "PETR4", "--format", "json", "--no-network"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)

    with open("docs/schema/cli_summary_schema.json", "r", encoding="utf-8") as f:
        schema = json.load(f)

    validate(instance=data, schema=schema)
