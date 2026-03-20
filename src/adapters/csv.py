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
from typing import ClassVar, List, Optional

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.errors import ValidationError


class CSVAdapter(Adapter):
    """Adapter that reads OHLCV data from a CSV file."""

    REQUIRED_COLUMNS: ClassVar[List[str]] = ["Open", "High", "Low", "Close", "Volume"]

    def _validate_dataframe(
        self,
        df: pd.DataFrame,
        ticker: str,
        required_columns: Optional[list[str]] = None,
    ) -> None:
        """Validate that required OHLCV columns are present before base checks."""
        if required_columns is None:
            required_columns = self.REQUIRED_COLUMNS

        # required_columns is now a concrete list[str] by construction, so we
        # can use it directly.
        if missing := [col for col in required_columns if col not in df.columns]:
            raise ValidationError(
                f"Missing required columns for CSVAdapter: {', '.join(missing)}"
            )

        # Reuse adapter's base class validation logic (including DatetimeIndex checks).
        super()._validate_dataframe(df, ticker, required_columns=required_columns)

    def _resolve_path(self, ticker: str) -> Path:
        """Resolve the CSV path for a ticker via env override, data dir, or fixture."""
        # Allow explicit override via environment variable for CI/notebook runs.
        if env_path := os.environ.get("CSV_ADAPTER_FILE"):
            env_path_obj = Path(env_path)
            if env_path_obj.exists():
                return env_path_obj
            raise FileNotFoundError(
                f"CSV_ADAPTER_FILE is set to {env_path!r} but file was not found. "
                "Please provide a valid path, or place CSV under dados/ or tests/fixtures/"  # noqa: E501
            )

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
        """Load CSV from path and normalize date/index + OHLCV columns.

        Args:
            path: CSV file path to read.

        Returns:
            DataFrame indexed by normalized ``date`` column.

        Behavior:
            - detects date column permissively in ('date','Date','DATE')
            - converts date column to datetime and injects as ``df['date']``
            - if source date column differs from "date", drops it before
              setting index to prevent redundant column retention
            - sets index via ``df.set_index('date')``
        """
        df = pd.read_csv(path)

        date_column = next(
            (
                candidate
                for candidate in ("date", "Date", "DATE")
                if candidate in df.columns
            ),
            None,
        )
        if date_column is None:
            raise ValidationError("CSV must contain a 'date' column")

        df["date"] = pd.to_datetime(df[date_column])
        if date_column != "date":
            df.drop(columns=[date_column], inplace=True)
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
        """Filter data by an inclusive date range.

        Parameters:
            df: pandas DataFrame with a DatetimeIndex.
            start: optional inclusive minimum date (e.g. '2024-01-01').
            end: optional inclusive maximum date (same format as start).

        Returns:
            Filtered DataFrame where rows satisfy ``start <= index <= end``.

        Notes:
            - if start is None, no lower bound is applied.
            - if end is None, no upper bound is applied.
            - index conversion is performed via ``pd.to_datetime``.
        """
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

    def _fetch_once(
        self,
        ticker: str,
        start: Optional[str],
        end: Optional[str],
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch data for a single time range and return validated DataFrame.

        This method delegates to `self.fetch` with `start_date` and `end_date`
        arguments and supports optional start/end boundaries (None means unbounded).

        Parameters:
            ticker: ticker symbol (e.g., 'PETR4').
            start: optional inclusive start date string.
            end: optional inclusive end date string.

        Returns:
            A pandas DataFrame with filtered and validated OHLCV data.
        """
        return self.fetch(ticker, start_date=start, end_date=end, **kwargs)
