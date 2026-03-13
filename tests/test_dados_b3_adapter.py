from typing import Optional

import pandas as pd
import pytest

from src.adapters.factory import get_adapter, register_adapter
from src.adapters.yfinance_adapter import YFinanceAdapter


def test_factory_returns_adapter_and_provider_override(monkeypatch):
    """O factory deve criar instâncias e respeitar o provider argument."""

    class Dummy(YFinanceAdapter):
        def fetch(self, ticker, start_date=None, end_date=None, **kwargs):
            return pd.DataFrame({"a": [1]})

    registry = {"yfinance": Dummy}
    monkeypatch.setattr("src.adapters.factory._ADAPTER_REGISTRY", registry)

    adapter = get_adapter("yfinance")
    assert isinstance(adapter, Dummy)
    df = adapter.fetch("PETR4.SA", start_date="2022-01-01", end_date="2022-12-31")
    assert not df.empty


def test_register_adapter_and_get(monkeypatch):
    """Verifica o registro de um adapter customizado e sua recuperação."""
    # isolar o registro global para que outros testes não sejam afetados
    monkeypatch.setattr("src.adapters.factory._ADAPTER_REGISTRY", {})

    class Dummy(YFinanceAdapter):
        # assina igual à classe-base para agradar ao type checker
        def fetch(
            self,
            ticker: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            **kwargs,
        ):
            return pd.DataFrame({"x": [1]})

    register_adapter("dummy", Dummy)
    adapter = get_adapter("dummy")
    assert isinstance(adapter, Dummy)


def test_register_adapter_raises_for_invalid_classes():
    """Garante que registrar classes inválidas dispara TypeError.

    O teste tenta registrar um objeto simples, uma classe sem herança e
    até uma instância para confirmar que apenas subclasses de Adapter são
    aceitas.
    """
    # garantimos que não registramos coisas que não são adapters válidos
    with pytest.raises(TypeError):
        # uso intencionalmente incorreto para o teste; o Pylance reclama
        register_adapter(
            "notaclass",
            object,  # tipo totalmente errado  # type: ignore[arg-type]
        )

    class NotAnAdapter:
        pass

    with pytest.raises(TypeError):
        register_adapter("notanadapter", NotAnAdapter)  # type: ignore

    # também asseguramos que instâncias são rejeitadas
    adapter_instance = YFinanceAdapter()
    with pytest.raises(TypeError):
        # passando um objeto em vez de uma classe; o type checker reclama
        register_adapter("instance", adapter_instance)  # type: ignore[arg-type]
