"""Simple factory for adapter instances.

Allows callers to obtain an adapter by name (e.g. "yfinance").
Future providers can be registered here; the map drives the CLI
"provider" option and unit tests can override the factory easily.
"""

import logging
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

    The provided ``adapter_cls`` must be a class (not an instance) and must
    subclass :class:`Adapter`.  We lowercase the key just as in
    :func:`get_adapter`.

    Raises
    ------
    TypeError
        if ``adapter_cls`` is not a subclass of :class:`Adapter` or is not a
        class at all.
    """
    # defensive validation to prevent silent registry corruption
    if not isinstance(adapter_cls, type):
        raise TypeError("adapter_cls must be a class")
    if not issubclass(adapter_cls, Adapter):
        raise TypeError(
            "adapter_cls must inherit from Adapter; got %r" % (adapter_cls,)
        )

    key = name.lower()
    if key in _ADAPTER_REGISTRY:
        # warn when overwriting existing registration to make accidental
        # collisions visible during startup/tests
        logging.getLogger(__name__).warning(
            "re-registering adapter %r, previous %r will be replaced",
            key,
            _ADAPTER_REGISTRY[key],
        )
    _ADAPTER_REGISTRY[key] = adapter_cls
