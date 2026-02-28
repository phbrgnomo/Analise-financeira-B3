"""Register a dummy provider and verify fetch for CI/local runs.

Usage:
  poetry run python scripts/register_dummy.py

This script registers a `dummy` adapter (inherits from `Adapter`) and
performs a quick fetch to ensure the registry and adapter shape are
correct for CI smoke tests.
"""


from src.adapters.dummy import DummyAdapter
from src.adapters.factory import get_adapter, register_adapter

# The script previously defined its own ``DummyAdapter`` class; we now
# centralize the implementation in ``src.adapters.dummy``.  The helper
# remains for CI smoke tests and local experimentation but simply imports
# the canonical class.

# Re-export for backwards compatibility with any external callers that
# might import the script module (unlikely but harmless).


# Using timezone-aware UTC now prevents the deprecation warning emitted by
# ``datetime.utcnow()`` in recent Python versions.

def register_and_check() -> None:
    register_adapter("dummy", DummyAdapter)
    adapter = get_adapter("dummy")
    print("Registered adapter:", adapter.__class__)
    df = adapter.fetch("TEST.SA")
    print("Columns:", list(df.columns))


if __name__ == "__main__":
    register_and_check()


def register_and_check() -> None:
    register_adapter("dummy", DummyAdapter)
    adapter = get_adapter("dummy")
    print("Registered adapter:", adapter.__class__)
    df = adapter.fetch("TEST.SA")
    print("Columns:", list(df.columns))


if __name__ == "__main__":
    register_and_check()
