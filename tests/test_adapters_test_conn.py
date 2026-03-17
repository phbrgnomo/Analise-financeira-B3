import types

from src.adapters import yfinance_adapter as yfa
from src.adapters.base import Adapter
from src.adapters.factory import get_adapter, register_adapter


def test_yfinance_test_connection_stub(monkeypatch):
    """When yfinance was stubbed at import-time, the adapter reports unavailable."""
    monkeypatch.setattr(yfa, "yf", types.SimpleNamespace(__is_stub__=True))
    adapter = yfa.YFinanceAdapter()
    assert adapter.test_connection() is False


def test_yfinance_test_connection_present(monkeypatch):
    """When yfinance module exposes expected attributes,
    test_connection returns True.
    """
    monkeypatch.setattr(
        yfa,
        "yf",
        types.SimpleNamespace(
            download=lambda *a, **k: None,
            Ticker=lambda *a, **k: None,
            __is_stub__=False,
        ),
    )
    adapter = yfa.YFinanceAdapter()
    assert adapter.test_connection() is True


def test_factory_shim_attached_for_adapters_without_method(monkeypatch):
    """get_adapter should attach a default test_connection shim to adapters
    that don't implement it, and the shim should be callable and return True.
    """
    # isolate registry
    monkeypatch.setattr("src.adapters.factory._ADAPTER_REGISTRY", {})

    class NoTest(Adapter):
        def fetch(self, ticker, **kwargs):
            return None

        def _fetch_once(self, ticker, start, end, **kwargs):
            return None

    register_adapter("notest", NoTest)
    adapter = get_adapter("notest")
    assert hasattr(adapter, "test_connection")
    assert callable(adapter.test_connection)
    assert adapter.test_connection() is True
