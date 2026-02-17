import subprocess
import sys


def test_main_help_exit_code_and_output():
    """Invoca `python -m src.main --help` e verifica saída e código de retorno."""
    completed = subprocess.run([sys.executable, "-m", "src.main", "--help"], capture_output=True, text=True)
    assert completed.returncode == 0
    assert "usage" in completed.stdout.lower() or "usage" in completed.stderr.lower()
