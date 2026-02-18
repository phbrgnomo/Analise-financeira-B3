import hashlib
import importlib
import os
import sys
import types
from pathlib import Path

import pandas as pd

# Provide a lightweight fake 'pandas_datareader' package to avoid heavy
# imports during test collection
pdreader = types.ModuleType("pandas_datareader")
pdreader.data = types.ModuleType("pandas_datareader.data")


def _dummy_datareader(*args, **kwargs):
    raise RuntimeError("DataReader should be monkeypatched in tests")


pdreader.data.DataReader = _dummy_datareader
sys.modules["pandas_datareader"] = pdreader
sys.modules["pandas_datareader.data"] = pdreader.data

dados_b3 = importlib.import_module("src.dados_b3")


def _write_snapshot(df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Ensure CSV matches fixture format: 'date' as first column (not index)
    df_out = df.copy()
    try:
        df_out.index.name = "date"
    except Exception:
        pass
    df_out = df_out.reset_index()
    df_out.to_csv(path, index=False)
    # compute sha256 checksum
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    checksum = h.hexdigest()
    with open(path + ".checksum", "w") as cf:
        cf.write(checksum)
    return checksum


def test_cotacao_ativo_dia_returns_mocked_dataframe(snapshot_dir, monkeypatch):
    # Arrange: create deterministic dataframe to be returned by the provider
    df = pd.DataFrame(
        {
            "Open": [10.0, 10.5],
            "High": [10.2, 10.6],
            "Low": [9.8, 10.1],
            "Close": [10.1, 10.4],
            "Adj Close": [10.1, 10.4],
            "Volume": [1000, 1500],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )

    # Monkeypatch the pandas_datareader DataReader used in src.dados_b3
    class MockWebDataProvider:
        @staticmethod
        def DataReader(*args, **kwargs):
            return df

    monkeypatch.setattr(dados_b3, "web", MockWebDataProvider)

    # Act
    result = dados_b3.cotacao_ativo_dia("PETR4", "2024-01-01", "2024-01-02")

    # Assert
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    # Ensure the returned DataFrame matches exactly the mocked data
    pd.testing.assert_frame_equal(result, df)

    # Save snapshot and checksum for CI artifact upload
    snap_path = os.path.join(snapshot_dir, "PETR4_snapshot.csv")
    checksum = _write_snapshot(result, snap_path)

    assert os.path.exists(snap_path)
    assert os.path.exists(snap_path + ".checksum")
    assert len(checksum) == 64

    # If an expected checksum fixture exists, compare to it to guard regression
    repo_root = Path(__file__).resolve().parents[2]
    expected_file = repo_root / "tests" / "fixtures" / "expected_snapshot.checksum"
    if expected_file.exists():
        expected = expected_file.read_text(encoding="utf-8").strip()
        assert checksum == expected


def test_snapshot_dir_is_temp(snapshot_dir):
    """Garante que `snapshot_dir` aponta para um diretório temporário.

    O diretório não deve estar dentro do repositório de trabalho
    para evitar commits acidentais.
    """
    import os
    import tempfile

    td = os.path.abspath(tempfile.gettempdir())
    sd = os.path.abspath(snapshot_dir)
    # Prefer a path-aware check for temp dir containment
    try:
        assert os.path.commonpath([td, sd]) == td
    except ValueError:
        # Fallback: compare prefix (robust on platforms where commonpath may raise)
        assert sd.startswith(td)
