"""Conftest de testes global.

Define fixtures úteis para integração e playback de rede.
"""
from __future__ import annotations

import os
from typing import Callable

import pandas as pd
import pytest

from tests.fixture_utils import create_prices_db_from_csv, get_or_make_snapshot_dir


def _load_sample_dataframe(ticker: str, start=None, end=None, **kwargs) -> pd.DataFrame:
    path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_ticker.csv")
    # CSV possui cabeçalho: usar nomes originais e converter 'date' para datetime
    df = pd.read_csv(path, parse_dates=["date"])  # uses header=0 by default
    df = df.set_index("date")
    # Garantir que o índice é DatetimeIndex
    df.index = pd.to_datetime(df.index, utc=False)

    # Normalizar nomes de colunas para formato esperado pelo adapter (provider style)
    col_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df = df.rename(columns=col_map)

    # Garantir colunas esperadas do provedor: Open, High, Low, Close, Volume
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = None

    # Não expor "Adj Close" nos dados de playback: DB não contém essa coluna.
    return df[["Open", "High", "Low", "Close", "Volume"]]


@pytest.fixture(autouse=True)
def mock_yfinance_data(monkeypatch) -> Callable:
    """Monkeypatch `src.adapters.yfinance_adapter.web.DataReader` para playback.

    Usa `tests/fixtures/sample_ticker.csv` como fonte determinística quando
    `NETWORK_MODE!=record`.
    """
    mode = os.environ.get("NETWORK_MODE", "playback").lower()
    if mode == "record":
        yield lambda *a, **k: None
        return

    def _patched_datareader(ticker, data_source=None, start=None, end=None, **kwargs):
        return _load_sample_dataframe(ticker, start=start, end=end, **kwargs)

    import src.adapters.yfinance_adapter as yadapter  # type: ignore

    ns = yadapter.types.SimpleNamespace(DataReader=_patched_datareader)
    monkeypatch.setattr(yadapter, "web", ns)
    yield _patched_datareader


@pytest.fixture(scope="function")
def sample_db():
    """Creates an in-memory SQLite DB seeded with tests/fixtures/sample_ticker.csv

    Yields a `sqlite3.Connection` object that tests can use.
    """
    db = create_prices_db_from_csv("sample_ticker.csv")

    try:
        yield db
    finally:
        # Ensure the connection is always closed after each test
        db.close()


@pytest.fixture(scope="function")
def sample_db_multi():
    """Creates an in-memory SQLite DB seeded with tests/fixtures/sample_ticker_multi.csv

    Yields a `sqlite3.Connection` object that tests can use.
    """
    db = create_prices_db_from_csv("sample_ticker_multi.csv")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def snapshot_dir(tmp_path_factory) -> str:
    """Diretório temporário (ou `SNAPSHOT_DIR` quando definido) para salvar
    snapshots gerados nos testes.

    Se a variável de ambiente `SNAPSHOT_DIR` estiver definida (ex.: em CI), usamos
    esse caminho e garantimos que ele exista; caso contrário, criamos um
    diretório temporário isolado.
    """

    env_path = os.environ.get("SNAPSHOT_DIR")
    return get_or_make_snapshot_dir(env_path, tmp_path_factory)
