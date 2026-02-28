"""Register a dummy provider and verify fetch for CI/local runs.

Usage:
  poetry run python scripts/register_dummy.py

This script registers a `dummy` adapter (inherits from `Adapter`) and
performs a quick fetch to ensure the registry and adapter shape are
correct for CI smoke tests.
"""

from datetime import datetime

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.factory import get_adapter, register_adapter


class DummyAdapter(Adapter):
    """Minimal adapter implementation for CI/local testing."""

    def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
        dates = pd.date_range(end=datetime.utcnow().date(), periods=3, freq="D")
        df = pd.DataFrame(
            {
                "Open": [1.0, 1.1, 1.2],
                "High": [1.0, 1.1, 1.2],
                "Low": [1.0, 1.1, 1.2],
                "Close": [1.0, 1.1, 1.2],
                "Adj Close": [1.0, 1.1, 1.2],
                "Volume": [100, 120, 110],
            },
            index=dates,
        )
        df.attrs["source"] = "dummy"
        return df

    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        return self.fetch(ticker, start=start, end=end, **kwargs)


def register_and_check() -> None:
    register_adapter("dummy", DummyAdapter)
    adapter = get_adapter("dummy")
    print("Registered adapter:", adapter.__class__)
    df = adapter.fetch("TEST.SA")
    print("Columns:", list(df.columns))


if __name__ == "__main__":
    register_and_check()
