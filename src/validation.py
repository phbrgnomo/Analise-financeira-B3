"""
Módulo de validação de DataFrames contra schema canônico.

Fornece validação de DataFrames, flagging de rows inválidas, e logging estruturado
de erros de validação para auditoria e debugging do pipeline de ingestão.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, cast

import numpy as np
import pandas as pd
from pandera.errors import SchemaError, SchemaErrors

from src.etl.mapper import CanonicalSchema

logger = logging.getLogger(__name__)


@dataclass
class ValidationSummary:
    """Summary of DataFrame validation results."""

    rows_total: int
    rows_valid: int
    rows_invalid: int
    invalid_percent: float
    error_codes_count: Dict[str, int]


class ValidationError(Exception):
    """Exception raised when validation threshold is exceeded."""

    pass


def _categorize_error(error_msg: str, column: str | None = None) -> str:
    """Map pandera error messages to human-readable reason codes.

    Args:
        error_msg: Error message from pandera
        column: Column name where error occurred (if known)

    Returns:
        Reason code string (e.g., 'MISSING_COL', 'BAD_DATE', 'NON_NUMERIC_PRICE')
    """
    error_lower = error_msg.lower()

    # Handle missing column errors
    if "column" in error_lower and (
        "not in" in error_lower or "missing" in error_lower
    ):
        return "MISSING_COL"

    # Handle type errors by column name and error content
    if column:
        col_lower = column.lower()
        if (col_lower == "date" or "date" in col_lower) and (
            "type" in error_lower or "datetime" in error_lower
        ):
            return "BAD_DATE"
        if col_lower in {"open", "high", "low", "close"} and (
            "float" in error_lower or "numeric" in error_lower
        ):
            return "NON_NUMERIC_PRICE"
        if col_lower == "volume":
            if "negative" in error_lower or "< 0" in error_lower:
                return "NEGATIVE_VOLUME"
            if "int" in error_lower or "numeric" in error_lower:
                return "NON_NUMERIC_VOLUME"

    # Generic type errors
    if "float" in error_lower or "int" in error_lower or "coerce" in error_lower:
        return "TYPE_ERROR"

    # Check constraint errors
    if "check" in error_lower or "constraint" in error_lower:
        return "CONSTRAINT_VIOLATION"

    # Default
    return "VALIDATION_ERROR"


def _extract_invalid_rows_from_schema_errors(
    df: pd.DataFrame, schema_errors: SchemaErrors
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Extract invalid rows and their error details from SchemaErrors.

    Args:
        df: Original DataFrame being validated
        schema_errors: SchemaErrors exception from pandera

    Returns:
        Tuple of (invalid_df, error_records)
        - invalid_df: DataFrame containing only invalid rows
        - error_records: List of dicts with error details for each invalid row
    """
    error_records = []
    invalid_indices = set()

    # Try to parse pandera failure_cases if available
    if (
        hasattr(schema_errors, "failure_cases")
        and schema_errors.failure_cases is not None
    ):
        failure_cases = schema_errors.failure_cases
        parsed_indices, parsed_records = _parse_failure_cases(failure_cases)
        if parsed_indices:
            invalid_indices.update(parsed_indices)
            error_records.extend(parsed_records)

    # If still no indices, run heuristics (e.g., high/low constraint)
    if not invalid_indices:
        h_indices, h_records = _heuristic_high_low_violations(df)
        if h_indices:
            invalid_indices.update(h_indices)
            error_records.extend(h_records)

    # If still nothing, mark all rows as potentially invalid with a generic message
    if not invalid_indices:
        error_msg = str(schema_errors)
        reason_code = _categorize_error(error_msg)
        for idx in df.index:
            invalid_indices.add(idx)
            error_records.append(
                {
                    "row_index": idx,
                    "column": None,
                    "reason_code": reason_code,
                    "reason_message": error_msg[:200],
                    "failure_value": None,
                }
            )

    # Build invalid_df from collected indices and return
    invalid_df = (
        df.loc[list(invalid_indices)].copy() if invalid_indices else pd.DataFrame()
    )

    return invalid_df, error_records


def _parse_failure_cases(failure_cases) -> Tuple[set, List[Dict[str, Any]]]:
    """Parse `failure_cases` DataFrame emitted by pandera into indices and records."""
    invalid_indices = set()
    error_records: List[Dict[str, Any]] = []
    for _, row in failure_cases.iterrows():
        index = row.get("index")
        column = row.get("column")
        check = row.get("check")
        failure_case = row.get("failure_case")

        error_msg = f"Column '{column}' failed check: {check}"
        reason_code = _categorize_error(str(check), column)

        if index is not None:
            invalid_indices.add(index)
            error_records.append(
                {
                    "row_index": index,
                    "column": column,
                    "reason_code": reason_code,
                    "reason_message": error_msg,
                    "failure_value": failure_case,
                }
            )

    return invalid_indices, error_records


def _heuristic_high_low_violations(
    df: pd.DataFrame,
) -> Tuple[set, List[Dict[str, Any]]]:
    """Detect high/low constraint violations and return indices + records."""
    invalid_indices = set()
    error_records: List[Dict[str, Any]] = []
    try:
        if "high" in df.columns and "low" in df.columns:
            mask_violation = ~(
                df["high"].isna()
                | df["low"].isna()
                | (df["high"] > df["low"])
            )
            positions = np.nonzero(mask_violation.to_numpy())[0]
            vio_idx = df.index[positions]
            if len(vio_idx) > 0:
                reason_code = "CONSTRAINT_VIOLATION"
                for idx in vio_idx:
                    invalid_indices.add(idx)
                    error_records.append(
                        {
                            "row_index": idx,
                            "column": "high,low",
                            "reason_code": reason_code,
                            "reason_message": "Constraint failed: high > low",
                            "failure_value": {
                                "high": df.at[idx, "high"],
                                "low": df.at[idx, "low"],
                            },
                        }
                    )
    except Exception:
        # Ignore heuristic failures and return empty
        return set(), []

    return invalid_indices, error_records


def _process_schema_exception(
    df: pd.DataFrame, exc: Exception
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Normalize pandera SchemaErrors or SchemaError into (invalid_df, error_records).

    This centralizes the logic used by `validate_dataframe` to keep complexity low.
    """
    # SchemaErrors (multiple failure_cases) or SchemaError (single) are both
    # handled here and return a consistent pair.
    if isinstance(exc, SchemaErrors):
        invalid_df, error_records = _extract_invalid_rows_from_schema_errors(df, exc)

        # Ensure generic error_records when failure_cases didn't provide details
        if not error_records and not invalid_df.empty:
            reason_code = _categorize_error(str(exc))
            error_records = []
            for idx in invalid_df.index:
                if pd.isna(cast(Any, idx)):
                    row_index = None
                else:
                    try:
                        row_index = int(cast(Any, idx))
                    except Exception:
                        row_index = idx

                error_records.append(
                    {
                        "row_index": row_index,
                        "column": None,
                        "reason_code": reason_code,
                        "reason_message": str(exc)[:200],
                        "failure_value": None,
                    }
                )

        return invalid_df, error_records

    # Single SchemaError: create per-row generic records and mark all rows invalid
    error_msg = str(exc)
    reason_code = _categorize_error(error_msg)
    error_records = [
        {
            "row_index": idx,
            "column": None,
            "reason_code": reason_code,
            "reason_message": error_msg[:200],
            "failure_value": None,
        }
        for idx in df.index
    ]
    invalid_df = df.copy()
    return invalid_df, error_records


def validate_dataframe(
    df: pd.DataFrame, schema=None, lazy: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, ValidationSummary]:
    """Validate DataFrame against canonical schema and separate valid/invalid rows.

    Args:
        df: DataFrame to validate (should be in canonical format)
        schema: Pandera schema to use (defaults to CanonicalSchema)
        lazy: If True, collect all errors before raising (default: True)

    Returns:
        Tuple of (valid_df, invalid_df, summary)
        - valid_df: DataFrame with only valid rows
        - invalid_df: DataFrame with only invalid rows (includes error metadata)
        - summary: ValidationSummary object with stats

    Raises:
        ValidationError: Never raised - function always returns results
    """
    if schema is None:
        schema = CanonicalSchema

    rows_total = len(df)

    # Handle empty DataFrame
    if rows_total == 0:
        summary = ValidationSummary(
            rows_total=0,
            rows_valid=0,
            rows_invalid=0,
            invalid_percent=0.0,
            error_codes_count={},
        )
        return df.copy(), pd.DataFrame(), summary

    try:
        # Attempt validation
        valid_df = schema.validate(df, lazy=lazy)

        # All rows valid
        summary = ValidationSummary(
            rows_total=rows_total,
            rows_valid=rows_total,
            rows_invalid=0,
            invalid_percent=0.0,
            error_codes_count={},
        )
        return valid_df, pd.DataFrame(), summary

    except SchemaErrors as e:
        logger.warning(f"Schema validation failed with SchemaErrors: {str(e)[:200]}")
        invalid_df, error_records = _process_schema_exception(df, e)
        valid_df = df.copy() if invalid_df.empty else df.drop(index=invalid_df.index)

    except SchemaError as e:
        logger.warning(f"Schema validation failed with SchemaError: {str(e)[:200]}")
        invalid_df, error_records = _process_schema_exception(df, e)
        valid_df = df.copy() if invalid_df.empty else df.drop(index=invalid_df.index)

    # Common handling for SchemaErrors or SchemaError:
    # build metadata, summary and return
    # Build error metadata for invalid rows
    if not invalid_df.empty:
        # Aggregate errors by row index
        errors_by_row = {}
        for rec in error_records:
            idx = rec["row_index"]
            if idx not in errors_by_row:
                errors_by_row[idx] = []
            errors_by_row[idx].append(rec)

        # Add error metadata to invalid_df
        invalid_df = invalid_df.copy()
        invalid_df["_validation_errors"] = invalid_df.index.map(
            lambda idx: errors_by_row.get(idx, [])
        )

    # Get valid rows (set difference)
    invalid_indices = set() if invalid_df.empty else set(invalid_df.index)
    valid_indices = [idx for idx in df.index if idx not in invalid_indices]
    valid_df = df.loc[valid_indices].copy() if valid_indices else pd.DataFrame()

    # Build summary
    rows_invalid = len(invalid_df)
    rows_valid = len(valid_df)
    invalid_percent = (rows_invalid / rows_total) if rows_total > 0 else 0.0

    # Count error codes
    error_codes_count = {}
    for rec in error_records:
        code = rec["reason_code"]
        error_codes_count[code] = error_codes_count.get(code, 0) + 1

    summary = ValidationSummary(
        rows_total=rows_total,
        rows_valid=rows_valid,
        rows_invalid=rows_invalid,
        invalid_percent=invalid_percent,
        error_codes_count=error_codes_count,
    )

    logger.info(
        f"Validation complete: {rows_valid}/{rows_total} valid "
        f"({invalid_percent:.1%} invalid). Error codes: {error_codes_count}"
    )

    return valid_df, invalid_df, summary


def check_threshold(
    summary: ValidationSummary, threshold: float = 0.10, abort_on_exceed: bool = True
) -> bool:
    """Check if invalid row percentage exceeds threshold.

    Args:
        summary: ValidationSummary from validate_dataframe
        threshold: Maximum allowed invalid percentage (0.0-1.0)
        abort_on_exceed: If True, raise ValidationError when exceeded

    Returns:
        True if within threshold, False if exceeded

    Raises:
        ValidationError: If threshold exceeded and abort_on_exceed=True
    """
    if summary.invalid_percent >= threshold:
        msg = (
            f"Validation threshold exceeded: {summary.invalid_percent:.1%} "
            f"invalid rows (threshold: {threshold:.1%}). "
            f"{summary.rows_invalid}/{summary.rows_total} rows invalid. "
            f"Error codes: {summary.error_codes_count}"
        )
        logger.error(msg)
        if abort_on_exceed:
            raise ValidationError(msg)
        return False

    return True


def _ensure_dir(path):
    import os

    os.makedirs(path, exist_ok=True)


def _normalize_threshold_value(threshold: float | None) -> float:
    import os

    if threshold is None:
        try:
            threshold_env = os.getenv("VALIDATION_INVALID_PERCENT_THRESHOLD")
            if threshold_env is not None:
                t = float(threshold_env)
                return (t / 100.0) if t > 1 else t
            return 0.10
        except Exception:
            return 0.10
    return threshold


def _coerce_dataframe_columns(df: pd.DataFrame) -> None:
    """In-place coercion of common column types used by validation."""
    # Normalize date
    if "date" in df.columns:
        with contextlib.suppress(Exception):
            df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    # Coerce numeric price columns
    numeric_cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
    for c in numeric_cols:
        with contextlib.suppress(Exception):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Volume as nullable integer when possible
    if "volume" in df.columns:
        with contextlib.suppress(Exception):
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")


def _flatten_invalid_error_records(invalid_df: pd.DataFrame) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    if invalid_df.empty or "_validation_errors" not in invalid_df.columns:
        return details

    for idx, errs in invalid_df["_validation_errors"].items():
        for e in errs:
            if pd.isna(cast(Any, idx)):
                row_index = None
            else:
                try:
                    row_index = int(cast(Any, idx))
                except Exception:
                    row_index = idx

            rec = {
                "row_index": row_index,
                "column": e.get("column"),
                "reason_code": e.get("reason_code"),
                "reason_message": e.get("reason_message"),
            }
            details.append(rec)

    return details


def _persist_and_log_invalids(
    invalid_df: pd.DataFrame,
    persist_invalid: bool,
    raw_root: str,
    provider: str,
    ticker: str,
    ts: str,
    metadata_path: str,
    raw_file: str,
    details: Dict[str, Any],
) -> str:
    invalid_filepath = ""
    if persist_invalid and not invalid_df.empty:
        invalid_filepath = persist_invalid_rows(
            invalid_df, raw_root, provider, ticker, ts
        )

    if not invalid_df.empty:
        entry = log_invalid_rows(
            metadata_path=metadata_path,
            provider=provider,
            ticker=ticker,
            raw_file=raw_file,
            invalid_filepath=invalid_filepath,
            error_records=details.get("error_records", []),
            job_id="",
        )
        details["ingest_log_entry"] = entry

    return invalid_filepath


def persist_invalid_rows(
    invalid_df: pd.DataFrame,
    raw_root: str,
    provider: str,
    ticker: str,
    ts: str,
    dest_folder: str | None = None,
) -> str:
    """Persist invalid rows to CSV and return filepath.

    The filename pattern follows: raw/<provider>/invalid-<ticker>-<ts>.csv
    Returns the written filepath as string.
    """
    import os

    if invalid_df is None or invalid_df.empty:
        return ""

    folder = dest_folder or (raw_root or "raw")
    folder = os.path.join(folder, provider)
    _ensure_dir(folder)

    filename = f"invalid-{ticker}-{ts}.csv"
    path = os.path.join(folder, filename)

    # Write CSV
    invalid_df.to_csv(path, index=True)

    # Compute checksum
    # checksum is intentionally omitted here (not used by callers)

    return path


def log_invalid_rows(
    metadata_path: str,
    provider: str,
    ticker: str,
    raw_file: str,
    invalid_filepath: str,
    error_records: list,
    job_id: str | None = None,
):
    """Append an entry to metadata/ingest_logs.json (JSON array) describing
    invalid rows.

    This is a lightweight implementation compatible with existing project
    patterns.
    """
    import json
    import os
    from datetime import datetime

    entry = {
        "job_id": job_id or "",
        "provider": provider,
        "ticker": ticker,
        "raw_file": raw_file,
        "invalid_filepath": invalid_filepath,
        "invalid_count": len(error_records) if error_records else 0,
        "error_details": error_records,
        "created_at": datetime.now().isoformat(),
    }

    if meta_dir := os.path.dirname(metadata_path):
        _ensure_dir(meta_dir)

    # Read existing array or create
    data = []
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as fh:
                data = json.load(fh) or []
        except Exception:
            data = []

    data.append(entry)

    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    return entry


def validate_and_handle(
    df: pd.DataFrame,
    provider: str,
    ticker: str,
    raw_file: str,
    ts: str,
    raw_root: str = "raw",
    metadata_path: str = "metadata/ingest_logs.json",
    threshold: float | None = None,
    abort_on_exceed: bool = True,
    persist_invalid: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, ValidationSummary, dict]:
    """Integration helper: validate dataframe, persist invalid rows,
    log results, and enforce threshold.

    Returns: valid_df, invalid_df, summary, details
    """

    # Normalize threshold and coerce common columns
    threshold = _normalize_threshold_value(threshold)
    _coerce_dataframe_columns(df)

    valid_df, invalid_df, summary = validate_dataframe(df)

    details: Dict[str, Any] = {
        "error_records": _flatten_invalid_error_records(invalid_df)
    }

    # Persist and log invalid rows if requested
    _persist_and_log_invalids(
        invalid_df=invalid_df,
        persist_invalid=persist_invalid,
        raw_root=raw_root,
        provider=provider,
        ticker=ticker,
        ts=ts,
        metadata_path=metadata_path,
        raw_file=raw_file,
        details=details,
    )

    # Enforce threshold
    try:
        check_threshold(summary, threshold=threshold, abort_on_exceed=abort_on_exceed)
    except ValidationError:
        # re-raise to caller
        raise

    return valid_df, invalid_df, summary, details
