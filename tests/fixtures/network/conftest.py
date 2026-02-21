"""Fixtures de rede para testes: modo `playback` (default) e `record`.

Fornece:
- `mock_yfinance_data` fixture: substitui
  `src.adapters.yfinance_adapter.web.DataReader` por uma função que carrega um CSV
  de fixtures (`tests/fixtures/sample_ticker.csv`).
- Variável de ambiente `NETWORK_MODE`: se `record`, a fixture não faz patch
  (usa yfinance real); no modo `playback` faz patch para retornar dados
  determinísticos.

Uso:
  - pytest (padrão): `NETWORK_MODE` não definido → `playback` (isolado)
  - Para atualizar gravações: `NETWORK_MODE=record pytest tests/..`
"""
from __future__ import annotations

import os
from typing import Callable

import pandas as pd
import pytest


def _load_sample_dataframe(ticker: str, start=None, end=None, **kwargs) -> pd.DataFrame:
    # Carrega CSV de fixtures e converte para DataFrame com índice datetime
    path = os.path.join(os.path.dirname(__file__), "..", "sample_ticker.csv")
    df = pd.read_csv(path, parse_dates=[1], header=None)
    # Arquivo sample_ticker.csv: ticker,date,open,high,low,close,volume,provider
    columns = [
      "ticker_col",
      "Date",
      "Open",
      "High",
      "Low",
      "Close",
      "Volume",
      "provider",
    ]
    df.columns = columns
    df = df.set_index("Date")
    # Ajuste de colunas para compatibilidade com yfinance: manter 'Close'.
    # Não expor 'Adj Close' nos dados de playback.
    # Garantir colunas esperadas
    for col in ["Open", "High", "Low", "Close", "Volume"]:
      if col not in df.columns:
        df[col] = None
    return df[["Open", "High", "Low", "Close", "Volume"]]


@pytest.fixture(autouse=False)
def mock_yfinance_data(monkeypatch) -> Callable:
    """Fixture que monkeypatches `src.adapters.yfinance_adapter.web.DataReader`.

    Para evitar chamadas de rede em CI, por padrão faz playback usando o CSV
    de fixtures. Setar `NETWORK_MODE=record` para desabilitar o patch e permitir
    requisições reais (útil apenas para atualização de gravações locais).
    """
    mode = os.environ.get("NETWORK_MODE", "playback").lower()

    if mode == "record":
        # Em modo record não patchamos, retorno None para sinalizar
        yield lambda *a, **k: None
        return

    # modo playback: patcha a função para carregar o CSV de fixtures
    def _patched_datareader(ticker, data_source=None, start=None, end=None, **kwargs):
        return _load_sample_dataframe(ticker, start=start, end=end, **kwargs)

    import src.adapters.yfinance_adapter as yadapter  # type: ignore

    ns = yadapter.types.SimpleNamespace(DataReader=_patched_datareader)
    monkeypatch.setattr(yadapter, "web", ns)

    yield _patched_datareader
