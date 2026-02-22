import os

import pandas as pd

from src.adapters.yfinance_adapter import YFinanceAdapter


def test_yfinance_adapter_playback(monkeypatch):
    # For clarity: ensure we're in playback mode for deterministic behavior
    os.environ.setdefault("NETWORK_MODE", "playback")

    adapter = YFinanceAdapter()
    df = adapter.fetch("PETR4.SA", start_date="2023-01-02", end_date="2023-01-06")

    assert isinstance(df, pd.DataFrame)
    # Expect non-empty DataFrame from fixture
    assert not df.empty
    # Check adapter metadata
    assert df.attrs.get("adapter") == "YFinanceAdapter"
    assert df.attrs.get("source") == "yahoo"
