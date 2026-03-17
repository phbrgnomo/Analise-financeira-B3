from src.adapters import yfinance_adapter as yfa
from src.adapters.base import Adapter
from src.adapters.factory import get_adapter, register_adapter


def test_yfinance_test_connection_stub(yfinance_stub):
    """When yfinance was stubbed at import-time, the adapter reports unavailable."""
    adapter = yfa.YFinanceAdapter()
    assert adapter.test_connection() is False


def test_yfinance_test_connection_present(yfinance_present):
    """When yfinance module exposes expected attributes,
    test_connection returns True.
    """
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
