import logging

from src.adapters.base import Adapter
from src.adapters.factory import get_adapter, register_adapter


def test_register_adapter_warns_on_replace(caplog, monkeypatch):
    # isolate registry
    monkeypatch.setattr('src.adapters.factory._ADAPTER_REGISTRY', {})

    class Dummy(Adapter):
        def fetch(self, ticker: str, **kwargs) -> None:
            return None

        def _fetch_once(self, ticker: str, start: str, end: str, **kwargs):
            return None

    # first registration should succeed quietly
    register_adapter('dummy', Dummy)
    # second registration of same name should emit warning
    caplog.set_level(logging.WARNING)
    register_adapter('dummy', Dummy)
    assert 're-registering adapter' in caplog.text.lower()

    # ensure get_adapter returns the class
    adapter = get_adapter('dummy')
    assert isinstance(adapter, Dummy)
