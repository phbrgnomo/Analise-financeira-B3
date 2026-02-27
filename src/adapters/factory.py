"""Simple factory for adapter instances.

Allows callers to obtain an adapter by name (e.g. "yfinance").
Future providers can be registered here; the map drives the CLI
"provider" option and unit tests can override the factory easily.
"""

from typing import Dict, Type

from src.adapters.base import Adapter
from src.adapters.yfinance_adapter import YFinanceAdapter

# dictionary of provider name (lowercase) -> Adapter class
_ADAPTER_REGISTRY: Dict[str, Type[Adapter]] = {
    "yfinance": YFinanceAdapter,
    "yahoo": YFinanceAdapter,  # alias for convenience
}


# public API

def get_adapter(name: str) -> Adapter:
    """Return a fresh adapter instance for the given provider name.

    Raises
    ------
    ValueError
        if the provider name is unknown.
    """
    name = name.lower()
    cls = _ADAPTER_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown adapter provider: {name!r}")
    return cls()


def register_adapter(name: str, adapter_cls: Type[Adapter]) -> None:
    """Register a new adapter class under the given name.

    Used by tests or startup code to make additional providers available.
    """
    _ADAPTER_REGISTRY[name.lower()] = adapter_cls
