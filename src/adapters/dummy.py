"""Lightweight "dummy" adapter used for CI smoke tests and local experiments.

This adapter is intentionally trivial: it returns a small, fixed DataFrame
with the expected OHLCV columns so that the ingestion machinery can exercise
its plumbing without relying on network access or third-party APIs.

The class also records whether ``fetch()`` was invoked via the ``called``
attribute, which is convenient for unit tests that monkeypatch the adapter
factory.

Having this adapter in ``src.adapters`` allows the factory to register it by
default, ensuring that commands like ``ingest_command(..., source="dummy")``
work even in fresh Python invocations.  The separate ``scripts/register_dummy.py``
helper still exists for backwards compatibility and manual verification.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pandas as pd

from src.adapters.base import Adapter


class DummyAdapter(Adapter):
    """Minimal provider that returns synthetic data and records usage.

    Attributes
    ----------
    called: bool
        Flag set to ``True`` when ``fetch`` is executed.  Tests may inspect
        this attribute to confirm that the factory returned the expected
        instance.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.called: bool = False

    def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Return a small constant DataFrame and mark ``called``.

        The returned DataFrame includes a timezone-aware index and the
        mandatory OHLCV columns.  ``kwargs`` are accepted but ignored to make
        the adapter flexible for tests using additional parameters.
        """
        self.called = True
        if sleep_secs := os.environ.get("DUMMY_SLEEP"):
            # somente a conversão para float deve falhar; deixe sleep() lançar
            # suas próprias exceções (e.g. KeyboardInterrupt) para que propaguem
            try:
                secs = float(sleep_secs)
            except ValueError:
                # ignore malformed value and continue without delay
                secs = 0.0
            else:
                if secs:
                    time.sleep(secs)
        dates = pd.date_range(
            end=datetime.now(timezone.utc).date(), periods=3, freq="D"
        )
        # choose values that satisfy the canonical schema requirement
        # (``high`` must be strictly greater than ``low`` unless one of them
        # is NaN or both are zero).  using a small offset keeps the sequence
        # deterministic and easy to inspect.
        df = pd.DataFrame(
            {
                "Open": [1.0, 1.1, 1.2],
                "High": [1.1, 1.2, 1.3],  # intentionally above "Low"
                "Low": [1.0, 1.05, 1.1],
                "Close": [1.0, 1.1, 1.2],
                "Adj Close": [1.0, 1.1, 1.2],
                "Volume": [100, 120, 110],
            },
            index=dates,
        )
        df.attrs["source"] = "dummy"
        return df

    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        # simply delegate to ``fetch`` since there is no retry logic here.
        return self.fetch(ticker, start=start, end=end, **kwargs)
