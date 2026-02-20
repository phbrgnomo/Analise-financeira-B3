"""
Canonical mapper: normalizes provider DataFrames to project's canonical schema.

This module provides:
- to_canonical(): main function to map raw provider DataFrame to canonical format
- CanonicalSchema: pandera schema for validation
- MappingError: exception for mapping failures
"""

import hashlib
import logging
from datetime import datetime, timezone

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema

logger = logging.getLogger(__name__)


class MappingError(Exception):
    """Exception raised when mapping from provider to canonical schema fails."""

    pass


# Pandera schema for canonical DataFrame validation
CanonicalSchema = DataFrameSchema(
    {
        "ticker": Column(str, nullable=False),
        "date": Column(pd.Timestamp, nullable=False),
        "open": Column(float, nullable=False),
        "high": Column(float, nullable=False),
        "low": Column(float, nullable=False),
        "close": Column(float, nullable=False),
        "adj_close": Column(float, nullable=False),
        "volume": Column(int, nullable=False, coerce=True),
        "source": Column(str, nullable=False),
        "fetched_at": Column(str, nullable=False),
    },
    strict=True,
    coerce=True,
)


def to_canonical(
    df: pd.DataFrame, provider_name: str, ticker: str
) -> pd.DataFrame:
    """
    Convert a raw provider DataFrame to the canonical schema.

    Args:
        df: Raw DataFrame from provider (typically with DatetimeIndex and OHLCV columns)
        provider_name: Name of the data provider (e.g., 'yfinance', 'alphavantage')
        ticker: Ticker symbol

    Returns:
        DataFrame with canonical columns: ticker, date, open, high, low, close,
        adj_close, volume, source, fetched_at

    Raises:
        MappingError: If required columns are missing, DataFrame is empty,
                     or validation fails

    Metadata:
        The returned DataFrame includes attrs:
        - raw_checksum: SHA256 hex digest of raw CSV representation
        - provider: provider_name
        - ticker: ticker symbol
    """
    # Validate input
    if df.empty:
        raise MappingError(f"Cannot map empty DataFrame for ticker {ticker}")

    # Check required columns (case-insensitive, provider-typical names)
    required_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise MappingError(
            f"Missing required columns for ticker {ticker}: {missing_cols}. "
            f"Available columns: {list(df.columns)}"
        )

    # Compute raw_checksum (SHA256 of CSV representation)
    csv_bytes = df.to_csv(index=True).encode("utf-8")
    raw_checksum = hashlib.sha256(csv_bytes).hexdigest()

    # Generate fetched_at timestamp (UTC ISO8601)
    fetched_at = datetime.now(timezone.utc).isoformat()

    # Build canonical DataFrame
    try:
        canonical_df = pd.DataFrame(
            {
                "ticker": ticker,
                "date": df.index,
                "open": df["Open"].values,
                "high": df["High"].values,
                "low": df["Low"].values,
                "close": df["Close"].values,
                "adj_close": df["Adj Close"].values,
                "volume": df["Volume"].values,
                "source": provider_name,
                "fetched_at": fetched_at,
            }
        )
    except (KeyError, ValueError, TypeError) as e:
        raise MappingError(
            f"Failed to construct canonical DataFrame for {ticker}: {e}"
        ) from e

    # Validate with pandera schema
    try:
        validated_df = CanonicalSchema.validate(canonical_df)
    except pa.errors.SchemaError as e:
        raise MappingError(
            f"Canonical schema validation failed for {ticker}: {e}"
        ) from e

    # Attach metadata to DataFrame attrs
    validated_df.attrs["raw_checksum"] = raw_checksum
    validated_df.attrs["provider"] = provider_name
    validated_df.attrs["ticker"] = ticker

    logger.info(
        f"Mapped {len(validated_df)} rows for {ticker} from {provider_name} "
        f"(checksum: {raw_checksum[:8]}...)"
    )

    return validated_df
