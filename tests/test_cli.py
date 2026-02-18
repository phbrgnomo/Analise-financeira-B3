import subprocess
import sys

from typer.testing import CliRunner

from src.main import app


def test_cli_help():
    """The `test_cli_help` function verifies the CLI help output.

    Ensures that invoking `--help` for the `app` displays the expected options.
    """
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Options:" in result.output


def test_main_help_exit_code_and_output():
    """Invoca `python -m src.main --help` e verifica saída e código de retorno."""
    completed = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0
    assert "usage" in completed.stdout.lower() or "usage" in completed.stderr.lower()
    # Help may emit deprecation warnings to stderr in some environments.
    # Ignore stderr content in the assertion.
