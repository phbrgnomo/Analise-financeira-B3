from typing import Optional

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
    # isolate the global registry so other tests aren't affected
    monkeypatch.setattr('src.adapters.factory._ADAPTER_REGISTRY', {})

    class Dummy(YFinanceAdapter):
        # match base class signature to keep type checkers happy
        def fetch(
            self,
            ticker: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            **kwargs,
        ):
            return pd.DataFrame({'x': [1]})

    register_adapter('dummy', Dummy)
    adapter = get_adapter('dummy')
    assert isinstance(adapter, Dummy)


def test_register_adapter_raises_for_invalid_classes():
    # ensure we don't accidentally register things that aren't proper adapters
    with pytest.raises(TypeError):
        # intentional misuse for test; Pylance complains about type mismatch
        register_adapter(
            'notaclass',
            object,  # wrong type entirely  # type: ignore[arg-type]
        )

    class NotAnAdapter:
        pass

    with pytest.raises(TypeError):
        register_adapter('notanadapter', NotAnAdapter) # type: ignore

    # also make sure instances are rejected
    adapter_instance = YFinanceAdapter()
    with pytest.raises(TypeError):
        # passing an object rather than a class; type checker complains
        register_adapter('instance', adapter_instance)  # type: ignore[arg-type]
