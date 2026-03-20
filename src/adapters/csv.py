"""Adapter that loads OHLCV data from a local CSV file.

This adapter is intended for deterministic, offline workflows such as
notebooks, CI, and local development where a sample dataset is available.

The file path can be configured via the environment variable
``CSV_ADAPTER_FILE``. If not set, the adapter will try the following paths
in order:

1. ``dados/{ticker}.csv``
2. ``tests/fixtures/ticker_example.csv`` (fallback sample)

The CSV is expected to contain at least the columns:
- ``date`` (parseable as a date)
- ``open``, ``high``, ``low``, ``close``, ``volume``

The resulting DataFrame will have a ``DatetimeIndex`` and include the
optional ``Adj Close`` column (copied from ``close`` if missing).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.errors import ValidationError


class CSVAdapter(Adapter):
    """Adapter that reads OHLCV data from a CSV file."""

    REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    def _resolve_path(self, ticker: str) -> Path:
        # Allow explicit override via environment variable for CI/notebook runs.
        if env_path := os.environ.get("CSV_ADAPTER_FILE"):
            return Path(env_path)

        # Prefer a file in the repository data directory named after the ticker.
        candidate = Path("dados") / f"{ticker}.csv"
        if candidate.exists():
            return candidate

        # Fall back to the canonical fixture sample.
        fixture = Path("tests") / "fixtures" / "ticker_example.csv"
        if fixture.exists():
            return fixture

        raise FileNotFoundError(
            f"Could not find CSV for ticker {ticker!r}. "
            "Set CSV_ADAPTER_FILE or add a CSV in dados/ or use the fixture."
        )

    def _load_dataframe(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)

        # Accept case-insensitive date column names (date/Date/DATE).
        date_column = None
        for candidate in ("date", "Date", "DATE"):
            if candidate in df.columns:
                date_column = candidate
                break

        if date_column is None:
            raise ValidationError("CSV must contain a 'date' column")

        df["date"] = pd.to_datetime(df[date_column])
        df = df.set_index("date")

        # Ensure case-insensitive OHLCV column names are normalized.
        canonical_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "adjclose": "Adj Close",
        }
        column_renames: dict[str, str] = {}
        for col in df.columns:
            normalized = str(col).strip().lower().replace(" ", "").replace("_", "")
            if normalized in canonical_map:
                column_renames[col] = canonical_map[normalized]

        if column_renames:
            df = df.rename(columns=column_renames)

        # Ensure Adj Close exists for downstream components that may rely on it.
        if "Adj Close" not in df.columns and "Close" in df.columns:
            df["Adj Close"] = df["Close"]

        return df

    def _filter_date_range(
        self, df: pd.DataFrame, start: Optional[str], end: Optional[str]
    ) -> pd.DataFrame:
        if start is not None:
            df = df[df.index >= pd.to_datetime(start)]
        if end is not None:
            df = df[df.index <= pd.to_datetime(end)]
        return df

    def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch data from CSV and return a validated DataFrame."""
        path = self._resolve_path(ticker)
        df = self._load_dataframe(path)

        # Apply optional date range filtering to mirror other adapters.
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        df = self._filter_date_range(df, start_date, end_date)

        df.attrs["source"] = "csv"

        # Validate into expected format for the pipeline.
        self._validate_dataframe(df, ticker)

        return df

    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        return self.fetch(ticker, start_date=start, end_date=end, **kwargs)
