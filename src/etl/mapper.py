"""
Canonical mapper: normalizes provider DataFrames to project's canonical schema.

This module provides:
- to_canonical(): main function to map raw provider DataFrame to canonical format
- CanonicalSchema: pandera schema for validation
- MappingError: exception for mapping failures
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera import Check
from pandera.pandas import Column, DataFrameSchema

logger = logging.getLogger(__name__)


class MappingError(Exception):
    """Exception raised when mapping from provider to canonical schema fails."""

    pass


# Load canonical schema from docs/schema.json (source of truth)


_TYPE_MAP = {
    "string": str,
    "date": pd.Timestamp,
    "datetime": str,
    "float": float,
    "int": int,
}


def _col_from_json(col_def: dict) -> Column:
    ctype = col_def.get("type")
    if ctype not in _TYPE_MAP:
        raise ValueError(f"Unknown type in canonical schema: {ctype!r}")
    dtype = _TYPE_MAP[ctype]
    nullable = bool(col_def.get("nullable", True))
    return Column(dtype, nullable=nullable, coerce=True)


def load_canonical_schema_from_json(path: Path) -> DataFrameSchema:
    data = json.loads(path.read_text())
    cols = {c["name"]: _col_from_json(c) for c in data.get("columns", [])}
    df_checks = []
    if "high" in cols and "low" in cols:
        # ensure that when present, high > low (ignore NaNs)
        df_checks.append(
            Check(
                lambda df: (
                    df["high"].isna()
                    | df["low"].isna()
                    | (df["high"] > df["low"])
                ).all(),
                element_wise=False,
            )
        )
    return DataFrameSchema(cols, strict=True, coerce=True, checks=df_checks)


_env_path = os.environ.get("CANONICAL_SCHEMA_PATH")
if _env_path:
    _schema_path = Path(_env_path)
else:
    _schema_path = Path(__file__).resolve().parents[2] / "docs" / "schema.json"

CanonicalSchema = load_canonical_schema_from_json(_schema_path)


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
                "raw_checksum": raw_checksum,
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
