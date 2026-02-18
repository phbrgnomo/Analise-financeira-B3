import hashlib
import importlib
import os
import sys
import types

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
    df.to_csv(path, index=True)
    # compute sha256 checksum
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    checksum = h.hexdigest()
    with open(path + ".checksum", "w") as cf:
        cf.write(checksum)
    return checksum


def test_cotacao_ativo_dia_mock(snapshot_dir, monkeypatch):
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
    class DummyWeb:
        @staticmethod
        def DataReader(*args, **kwargs):
            return df

    monkeypatch.setattr(dados_b3, "web", DummyWeb)

    # Act
    result = dados_b3.cotacao_ativo_dia("PETR4", "2024-01-01", "2024-01-02")

    # Assert
    assert isinstance(result, pd.DataFrame)
    assert not result.empty

    # Save snapshot and checksum for CI artifact upload
    snap_path = os.path.join(snapshot_dir, "PETR4_snapshot.csv")
    checksum = _write_snapshot(result, snap_path)

    assert os.path.exists(snap_path)
    assert os.path.exists(snap_path + ".checksum")
    assert len(checksum) == 64
