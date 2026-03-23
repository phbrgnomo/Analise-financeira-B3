"""
Canonical mapper: normalizes provider DataFrames to the project's canonical schema.

Behavior:
- Loads canonical schema from docs/schema.json (the project's source of truth) and
  builds a pandera.DataFrameSchema.
- to_canonical() constructs a canonical DataFrame using the schema column
  order/types, maps provider columns to canonical names, injects computed fields
  (fetched_at, raw_checksum), and validates using the loaded schema.

Helpers:
- load_canonical_schema_from_json(path) -> DataFrameSchema: builds the pandera
  schema from JSON.

Notes:
- Provider-to-canonical mapping is best kept in adapters; this mapper contains a
  minimal heuristic mapping for common providers (yfinance).
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

import pandas as pd
from pandera import Check
from pandera.errors import SchemaError
from pandera.pandas import Column, DataFrameSchema

logger = logging.getLogger(__name__)


def parse_date_strict(date_str: str) -> datetime:
    """Parse an ISO date string (YYYY-MM-DD) strictly and return a UTC-aware
    datetime at midnight UTC.

    Rules:
    - Accepts only the exact format '%Y-%m-%d' when given a string.
    - Accepts datetime or pandas.Timestamp values as well and normalizes
      them to UTC.
    - Rejects dates in the future (strictly greater than now UTC).
    - Rejects dates before 2000-01-01.

    Raises ValueError on any violation.
    """
    if isinstance(date_str, pd.Timestamp):
        dt = date_str.to_pydatetime()
    elif isinstance(date_str, datetime):
        dt = date_str
    elif isinstance(date_str, str):
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception as e:  # ValueError from strptime
            raise ValueError(
                f"Invalid date format, expected YYYY-MM-DD: {date_str}"
            ) from e
    else:
        raise ValueError(f"Unsupported date type: {type(date_str)!r}")

    # Normalize to timezone-aware UTC using pandas.Timestamp helpers to avoid
    # edge-case differences between naive and aware datetimes.
    ts = pd.Timestamp(dt)
    if ts.tzinfo is None:
        ts = ts.tz_localize(timezone.utc)
    else:
        ts = ts.tz_convert(timezone.utc)

    # Normalize to midnight UTC (date affinity)
    ts = ts.normalize()
    dt = ts.to_pydatetime()

    now = datetime.now(timezone.utc)
    if dt > now:
        raise ValueError(f"Date is in the future: {dt.isoformat()}")

    min_allowed = datetime(2000, 1, 1, tzinfo=timezone.utc)
    if dt < min_allowed:
        raise ValueError(f"Date before allowed minimum (2000-01-01): {dt.date()}")

    return dt


class MappingError(Exception):
    """Exception raised when mapping from provider to canonical schema fails."""

    pass


# Load canonical schema from docs/schema.json (source of truth)


_TYPE_MAP = {
    "string": str,
    "date": pd.Timestamp,
    "datetime": pd.Timestamp,
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


def load_canonical_schema_from_json(path_or_dict: Union[Path, dict]) -> DataFrameSchema:
    """Build a pandera DataFrameSchema from a file path or an already-loaded dict.

    Accepting a dict avoids re-reading the JSON file when the caller already
    parsed it (useful for tests or when the module wants to reuse the
    parsed schema for other purposes).
    """
    if isinstance(path_or_dict, dict):
        data = path_or_dict
    else:
        data = json.loads(path_or_dict.read_text())

    cols = {c["name"]: _col_from_json(c) for c in data.get("columns", [])}
    df_checks = []
    if "high" in cols and "low" in cols:
        # ensure that when present, high > low (ignore NaNs).
        # yfinance occasionally returns 0 for both high and low on non-trading
        # days; treat those rows as benign rather than failing validation.
        df_checks.append(
            Check(
                lambda df: (
                    df["high"].isna()
                    | df["low"].isna()
                    | (df["high"] > df["low"])
                    | ((df["high"] == 0) & (df["low"] == 0))
                ).all(),
                element_wise=False,
            )
        )
    # Allow extra columns (e.g., adj_close) to be present in DataFrames
    # even if they are not part of the final DB schema. Validation will
    # still enforce types for known columns.
    return DataFrameSchema(cols, strict=False, coerce=True, checks=df_checks)


def _determine_schema_cols() -> list:
    """Return schema columns list with adj_close inserted if necessary."""
    # Respect the canonical schema defined in docs/schema.json strictly.
    # Do not inject additional columns (e.g., adj_close) that are not present
    # in the schema JSON. The schema file is the source of truth for columns
    # persisted/stable across the pipeline.
    return [c.get("name") for c in _SCHEMA_JSON.get("columns", [])]


def _col_lookup_in_df(df: pd.DataFrame, columns_map: dict, candidate: str):
    # Prefer matching against the normalized columns_map where keys are
    # lowercased strings of the original column labels. This avoids errors
    # when df.columns contains non-string labels (e.g., DatetimeIndex).
    key = candidate.lower()
    if key in columns_map:
        return columns_map[key]
    alt = key.replace(" ", "_")
    if alt in columns_map:
        return columns_map[alt]
    # As a fallback, allow exact object membership checks.
    return candidate if candidate in df.columns else None


def _pick_provider_values(
    df: pd.DataFrame,
    columns_map: dict,
    col_candidates,
    nrows: int,
):
    for c in col_candidates:
        actual = _col_lookup_in_df(df, columns_map, c)
        if actual is not None:
            return df[actual].values
    return [pd.NA] * nrows


def _build_canonical_data(
    df: pd.DataFrame, meta: dict, nrows: int, columns_map: dict
) -> dict:
    """Construct canonical-data dict including optional adj_close handling.

    Separated into a helper to reduce complexity of `to_canonical`.
    """
    data = {}
    schema_cols = _determine_schema_cols()

    for name in schema_cols:
        val = _fill_special_values(df, name, meta, nrows)
        if val is not None:
            data[name] = val
            continue
        candidates = _CANON_TO_PROVIDER.get(name, [name, name.capitalize()])
        data[name] = _pick_provider_values(df, columns_map, candidates, nrows)

    return data


_env_path = os.environ.get("CANONICAL_SCHEMA_PATH")
if _env_path:
    _schema_path = Path(_env_path)
else:
    _schema_path = Path(__file__).resolve().parents[2] / "docs" / "schema.json"

# Read schema JSON once and reuse it to build the pandera schema and to
# determine column order. This avoids reading/parsing the file multiple
# times during import and makes it simple to inject a pre-parsed schema for
# tests or multi-schema scenarios.
_SCHEMA_JSON = json.loads(_schema_path.read_text())
CanonicalSchema = load_canonical_schema_from_json(_SCHEMA_JSON)

# Minimal provider candidates for common canonical columns. Adapters can
# provide a more complete mapping if needed.
_CANON_TO_PROVIDER = {
    "open": ["Open", "open"],
    "high": ["High", "high"],
    "low": ["Low", "low"],
    "close": ["Close", "close"],
    "volume": ["Volume", "volume"],
    "adj_close": ["Adj Close", "adj_close"],
}


def _fill_special_values(df: pd.DataFrame, name: str, meta: dict, nrows: int):
    """Fill values for schema fields that are computed or come from metadata.

    meta: dictionary with keys 'ticker','provider_name','fetched_at','raw_checksum'.
    """
    if name == "date":
        date_col = next((c for c in df.columns if str(c).lower() == "date"), None)
        # Validate and normalize each date value strictly. Invalid dates are
        # logged and replaced with pandas.NaT so downstream validation can
        # decide on rejecting rows while keeping mapping deterministic.
        values = df[date_col] if date_col is not None else df.index
        normalized = []
        for v in values:
            try:
                dt = parse_date_strict(v)
                normalized.append(pd.Timestamp(dt))
            except ValueError as exc:
                logger.warning("Rejected date value during mapping: %s (%s)", v, exc)
                normalized.append(pd.NaT)

        return pd.to_datetime(pd.Series(normalized))
    if name == "ticker":
        return [meta["ticker"]] * nrows
    if name == "source":
        return [meta["provider_name"]] * nrows
    if name == "fetched_at":
        return [meta["fetched_at"]] * nrows
    return [meta["raw_checksum"]] * nrows if name == "raw_checksum" else None


def to_canonical(
    df: pd.DataFrame,
    provider_name: str,
    ticker: str,
    raw_checksum: str | None = None,
    fetched_at: str | None = None,
) -> pd.DataFrame:
    """
    Convert a raw provider DataFrame to the canonical schema.

    Args:
        df: Raw DataFrame from provider (typically with DatetimeIndex and OHLCV columns)
        provider_name: Name of the data provider (e.g., 'yfinance', 'alphavantage')
        ticker: Ticker symbol

    Returns:
        DataFrame with canonical columns: ticker, date, open, high, low, close,
        volume, source, fetched_at

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

    # Build case-insensitive column map to allow provider variations
    # Use str(c).lower() to avoid failures when column labels are not strings
    columns_map = {str(c).lower(): c for c in df.columns}

    # Note: 'Adj Close' is optional in provider responses; canonical schema allows
    # adj_close to be nullable. Require only the primary OHLCV columns here.
    required_cols_lower = ["open", "high", "low", "close", "volume"]
    if missing_cols := [col for col in required_cols_lower if col not in columns_map]:
        raise MappingError(
            f"Missing required columns for ticker {ticker}: {missing_cols}. "
            f"Available columns: {list(df.columns)}"
        )

    # Compute or reuse raw_checksum (SHA256 of a deterministic CSV representation)
    if raw_checksum is None:
        raw_csv = (
            df.sort_index()
            .to_csv(
                index=True,
                date_format="%Y-%m-%dT%H:%M:%S",
                float_format="%.10g",
                na_rep="",
            )
            .encode("utf-8")
        )
        raw_checksum = hashlib.sha256(raw_csv).hexdigest()

    # Generate fetched_at timestamp (UTC ISO8601 with 'Z') if not provided
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Build canonical DataFrame using the canonical schema JSON for column
    # order and names. This avoids duplicating the canonical contract in code.
    try:
        nrows = len(df)
        data = {}

        meta = {
            "ticker": ticker,
            "provider_name": provider_name,
            "fetched_at": fetched_at,
            "raw_checksum": raw_checksum,
        }

        data = _build_canonical_data(df, meta, nrows, columns_map)

        canonical_df = pd.DataFrame(data)

        # Enforce schema invariant: high >= low. Some providers occasionally
        # return corrupted rows where high < low — swap values and log a
        # warning per-row when this occurs so downstream consumers get
        # consistent data instead of failing validation.
        if "high" in canonical_df.columns and "low" in canonical_df.columns:
            mask = (
                canonical_df["high"].notna()
                & canonical_df["low"].notna()
                & (canonical_df["high"] < canonical_df["low"])
            )
            if mask.any():
                for idx in canonical_df[mask].index:
                    old_high = canonical_df.at[idx, "high"]
                    old_low = canonical_df.at[idx, "low"]
                    # swap
                    canonical_df.at[idx, "high"] = old_low
                    canonical_df.at[idx, "low"] = old_high
                    date_val = (
                        canonical_df.at[idx, "date"]
                        if "date" in canonical_df.columns
                        else None
                    )
                    # format date for log (keep original object string if None)
                    date_str = (
                        str(date_val.date())
                        if hasattr(date_val, "date")
                        else str(date_val)
                    )
                    logger.warning(
                        "High/low swap for ticker %s on %s: high=%s low=%s -> high=%s low=%s",
                        ticker,
                        date_str,
                        old_high,
                        old_low,
                        canonical_df.at[idx, "high"],
                        canonical_df.at[idx, "low"],
                    )

        # After ensuring high/low invariants, detect large open/close
        # intraday moves (outliers). Preserve rows; we only log and count.
        if "open" in canonical_df.columns and "close" in canonical_df.columns:
            for idx in canonical_df.index:
                try:
                    o = canonical_df.at[idx, "open"]
                    c = canonical_df.at[idx, "close"]
                    date_val = (
                        canonical_df.at[idx, "date"]
                        if "date" in canonical_df.columns
                        else None
                    )
                except Exception:
                    continue
                # Call detect_outlier which logs and increments counter when
                # appropriate. We intentionally ignore the return value here
                # because the pipeline should not reject rows.
                try:
                    detect_outlier(o, c, ticker=ticker, date_val=date_val)
                except Exception:
                    # Detection should never raise; protect mapping pipeline
                    logger.warning(
                        "Outlier detection failed for %s on %s", ticker, date_val
                    )
    except (KeyError, ValueError, TypeError) as e:
        raise MappingError(
            f"Failed to construct canonical DataFrame for {ticker}: {e}"
        ) from e

    # Validate with pandera schema
    try:
        validated_df = CanonicalSchema.validate(canonical_df)
    except SchemaError as e:
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
