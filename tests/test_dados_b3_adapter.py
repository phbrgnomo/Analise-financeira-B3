import pandas as pd
import pytest

from src.adapters.factory import get_adapter, register_adapter
from src.adapters.yfinance_adapter import YFinanceAdapter


def test_factory_returns_adapter_and_provider_override(monkeypatch):
    """O factory deve criar instâncias e respeitar o provider argument."""
    class Dummy(YFinanceAdapter):
        def fetch(self, ticker, start_date=None, end_date=None, **kwargs):
            return pd.DataFrame({'a': [1]})

    monkeypatch.setattr('src.adapters.factory._ADAPTER_REGISTRY', {'yahoo': Dummy})

    adapter = get_adapter('yahoo')
    assert isinstance(adapter, Dummy)
    df = adapter.fetch('PETR4.SA', start_date='2022-01-01', end_date='2022-12-31')
    assert not df.empty


def test_register_adapter_and_get(monkeypatch):
    class Dummy(YFinanceAdapter):
        def fetch(self, ticker, **kwargs):
            return pd.DataFrame({'x': [1]})

    register_adapter('dummy', Dummy)
    adapter = get_adapter('dummy')
    assert isinstance(adapter, Dummy)


def test_deprecation_warning_on_dados_b3_import(monkeypatch):
    # import inside capture to check warning
    with pytest.warns(DeprecationWarning):
        import importlib

        importlib.reload(__import__('src.dados_b3'))
