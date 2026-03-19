import logging

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.factory import get_adapter, register_adapter


def test_register_adapter_warns_on_replace(caplog, monkeypatch):
    # isolate registry
    monkeypatch.setattr("src.adapters.factory._ADAPTER_REGISTRY", {})

    class Dummy(Adapter):
        def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
            # Return an empty DataFrame to satisfy the base class contract.
            return pd.DataFrame()

        def _fetch_once(
            self,
            ticker: str,
            start: str,
            end: str,
            **kwargs
            ) -> pd.DataFrame:
            return pd.DataFrame()

    # first registration should succeed quietly
    register_adapter("dummy", Dummy)
    # second registration of same name should emit warning
    caplog.set_level(logging.WARNING)
    register_adapter("dummy", Dummy)
    assert "re-registering adapter" in caplog.text.lower()

    # ensure get_adapter returns the class
    adapter = get_adapter("dummy")
    assert isinstance(adapter, Dummy)


def test_available_providers_reflects_registry(monkeypatch) -> None:
    """Test that available_providers() returns all registered adapter names.

    The results should be sorted to make the behavior predictable.
    """
    # isolate registry and add two entries
    monkeypatch.setattr("src.adapters.factory._ADAPTER_REGISTRY", {})

    class A(Adapter):
        def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
            return pd.DataFrame()

        def _fetch_once(
            self,
            ticker: str,
            start: str,
            end: str,
            **kwargs
            ) -> pd.DataFrame:
            return pd.DataFrame()

    class B(Adapter):
        def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
            return pd.DataFrame()

        def _fetch_once(
            self,
            ticker: str,
            start: str,
            end: str,
            **kwargs
            ) -> pd.DataFrame:
            return pd.DataFrame()

    from src.adapters.factory import available_providers

    register_adapter("one", A)
    register_adapter("two", B)

    provs = available_providers()
    assert "one" in provs and "two" in provs
    # result is sorted, so order should be predictable
    assert provs == ["one", "two"]
