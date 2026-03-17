"""Simple factory for adapter instances.

Allows callers to obtain an adapter by name (e.g. "yfinance").
Future providers can be registered here; the map drives the CLI
"provider" option and unit tests can override the factory easily.
"""

import logging
from typing import Dict, Type

from src.adapters.base import Adapter

# import dummy adapter so it can be registered by default.  doing this here
# keeps tests and the CI smoke test simple: the provider ``dummy`` is always
# available without requiring an explicit registration step in the same
# Python process.
from src.adapters.dummy import DummyAdapter
from src.adapters.yfinance_adapter import YFinanceAdapter

# dictionary of provider name (lowercase) -> Adapter class
_ADAPTER_REGISTRY: Dict[str, Type[Adapter]] = {
    "yfinance": YFinanceAdapter,
    # alias "yahoo" removido – use apenas "yfinance". Esta é uma mudança
    # incompatível (breaking change); quaisquer scripts ou integrações que
    # referenciavam "yahoo" anteriormente devem migrar.
    "dummy": DummyAdapter,  # synthetic provider used for smoke tests
}


# public API


def available_providers() -> list[str]:
    """Return a list of currently registered provider names.

    The result is suitable for use in CLI help text or validation.  Aliases
    are included; callers may wish to dedupe or sort as needed.
    """
    return sorted(_ADAPTER_REGISTRY.keys())


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
    inst = cls()
    # Ensure adapters without a dedicated test_connection expose a default
    # shim so `main test-conn` remains useful even when adapters haven't been
    # updated to include the method.
    if not hasattr(inst, "test_connection") or not callable(inst.test_connection):
        import types

        def _default_test_connection(self) -> bool:
            logging.getLogger(__name__).debug(
                "Adapter %s has no test_connection; using default shim "
                "(assume healthy)",
                name,
            )
            return True

        inst.test_connection = types.MethodType(_default_test_connection, inst)
    return inst


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
