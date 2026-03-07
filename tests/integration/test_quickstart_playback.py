import os

import pandas as pd

from src.adapters.yfinance_adapter import YFinanceAdapter


def test_yfinance_adapter_playback(monkeypatch):
    """Verifica que o adapter do yfinance funciona em modo playback.

    O teste força a variável de ambiente `NETWORK_MODE` para "playback" para
    garantir comportamento determinístico usando os fixtures de rede. Deve
    retornar um DataFrame não vazio com atributos de metadata corretos.
    """
    # para deixar claro: garantimos modo playback para comportamento determinístico
    os.environ.setdefault("NETWORK_MODE", "playback")

    adapter = YFinanceAdapter()
    df = adapter.fetch("PETR4.SA", start_date="2023-01-02", end_date="2023-01-06")

    assert isinstance(df, pd.DataFrame)
    # espera DataFrame não vazio vindo do fixture
    assert not df.empty
    # verifica metadata do adapter
    assert df.attrs.get("adapter") == "YFinanceAdapter"
    assert df.attrs.get("source") == "yfinance"
