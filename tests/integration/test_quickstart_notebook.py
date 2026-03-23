import os
from pathlib import Path

import pandas as pd
import pytest


@pytest.mark.skipif(
    os.environ.get("PAPERMILL") != "1",
    reason="Set PAPERMILL=1 to run notebook integration tests",
)
def test_quickstart_notebook_runs_and_produces_returns(tmp_path, monkeypatch):
    """Run the quickstart notebook end-to-end and validate output artifacts."""

    pm = pytest.importorskip("papermill")

    repo_root = Path(__file__).resolve().parents[2]
    notebook_path = repo_root / "examples" / "notebooks" / "quickstart.ipynb"
    assert notebook_path.exists(), "Quickstart notebook not found"

    csv_adapter_file = repo_root / "tests" / "fixtures" / "ticker_example.csv"
    assert csv_adapter_file.exists(), "Quickstart CSV fixture not found"
    monkeypatch.setenv("CSV_ADAPTER_FILE", str(csv_adapter_file))

    output_dir = tmp_path / "notebook_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    out_nb = tmp_path / "quickstart-output.ipynb"

    pm.execute_notebook(
        str(notebook_path),
        str(out_nb),
        parameters={
            "tickers": ["PETR4"],
            "output_dir": str(output_dir),
            "csv_path": str(csv_adapter_file),
        },
    )

    returns_csv = output_dir / "PETR4_returns.csv"
    assert returns_csv.exists(), "Expected returns CSV to be generated"

    df = pd.read_csv(returns_csv)
    assert "return_value" in df.columns
    assert not df.empty
    assert pd.api.types.is_numeric_dtype(df["return_value"])
