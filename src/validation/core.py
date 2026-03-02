"""Core validation: schema validation, error extraction, threshold, coercion."""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Dict, List, Tuple, cast

import numpy as np
import pandas as pd
from pandera.errors import SchemaError, SchemaErrors

from src.etl.mapper import CanonicalSchema
from src.validation.errors import (
    ErrorRecords,
    IndexSet,
    ValidationError,
    ValidationSummary,
    _categorize_error,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error extraction from pandera
# ---------------------------------------------------------------------------


def _extract_invalid_rows_from_schema_errors(
    df: pd.DataFrame, schema_errors: SchemaErrors
) -> Tuple[pd.DataFrame, ErrorRecords]:
    """Extract invalid rows and their error details from SchemaErrors.

    Args:
        df: Original DataFrame being validated
        schema_errors: SchemaErrors exception from pandera

    Returns:
        Tuple of (invalid_df, error_records)
    """
    error_records: ErrorRecords = []
    invalid_indices: set = set()

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

    # If still nothing, emit a single schema-level error record
    if not invalid_indices:
        error_msg = str(schema_errors)
        reason_code = _categorize_error(error_msg)

        error_records.append(
            {
                "row_index": None,
                "column": None,
                "reason_code": reason_code,
                "reason_message": error_msg[:200],
                "failure_value": None,
            }
        )

    # Build invalid_df from collected indices and return
    invalid_df = (
        df.loc[list(invalid_indices)].copy()
        if invalid_indices
        else pd.DataFrame()
    )

    return invalid_df, error_records


def _parse_failure_cases(
    failure_cases,
) -> Tuple[IndexSet, ErrorRecords]:
    """Parse ``failure_cases`` DataFrame emitted by pandera into indices and records."""
    invalid_indices: IndexSet = set()
    error_records: ErrorRecords = []
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
) -> Tuple[IndexSet, ErrorRecords]:
    """Detect high/low constraint violations and return indices + records."""
    invalid_indices: set = set()
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
                            "reason_message": (
                                "Constraint failed: high > low"
                            ),
                            "failure_value": {
                                "high": df.at[idx, "high"],
                                "low": df.at[idx, "low"],
                            },
                        }
                    )
    except Exception as exc:
        logger.debug(
            "Heuristic high/low check failed: %s", exc, exc_info=True
        )
        return set(), []

    return invalid_indices, error_records


def _process_schema_exception(
    df: pd.DataFrame, exc: Exception
) -> Tuple[pd.DataFrame, ErrorRecords]:
    """Normalize pandera SchemaErrors or SchemaError into (invalid_df, error_records).

    This centralizes the logic used by ``validate_dataframe`` to keep
    complexity low.
    """
    if isinstance(exc, SchemaErrors):
        invalid_df, error_records = (
            _extract_invalid_rows_from_schema_errors(df, exc)
        )

        # If failure_cases didn't provide row indices but the error is a
        # missing-column type, mark all rows invalid (legacy behaviour).
        if invalid_df.empty:
            reason_code = _categorize_error(str(exc))
            if reason_code == "MISSING_COL":
                error_records = [
                    {
                        "row_index": idx,
                        "column": None,
                        "reason_code": reason_code,
                        "reason_message": str(exc)[:200],
                        "failure_value": None,
                    }
                    for idx in df.index
                ]
                invalid_df = df.copy()

        # Ensure generic error_records when failure_cases didn't provide
        # details
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

    # Single SchemaError: create per-row generic records and mark all rows
    # invalid
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


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------


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
        logger.warning(
            "Schema validation failed with SchemaErrors: %s",
            str(e)[:200],
        )
        invalid_df, error_records = _process_schema_exception(df, e)
        valid_df = (
            df.copy() if invalid_df.empty else df.drop(index=invalid_df.index)
        )

    except SchemaError as e:
        logger.warning(
            "Schema validation failed with SchemaError: %s",
            str(e)[:200],
        )
        invalid_df, error_records = _process_schema_exception(df, e)
        valid_df = (
            df.copy() if invalid_df.empty else df.drop(index=invalid_df.index)
        )

    # Common handling for SchemaErrors or SchemaError:
    # build metadata, summary and return
    if not invalid_df.empty:
        # Aggregate errors by row index
        errors_by_row: Dict[Any, list] = {}
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
    valid_indices = [
        idx for idx in df.index if idx not in invalid_indices
    ]
    valid_df = (
        df.loc[valid_indices].copy() if valid_indices else pd.DataFrame()
    )

    # Build summary
    rows_invalid = len(invalid_df)
    rows_valid = len(valid_df)
    invalid_percent = (rows_invalid / rows_total) if rows_total > 0 else 0.0

    # Count error codes
    error_codes_count: Dict[str, int] = {}
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
        "Validation complete: %d/%d valid (%.1f%% invalid). Error codes: %s",
        rows_valid,
        rows_total,
        invalid_percent * 100,
        error_codes_count,
    )

    return valid_df, invalid_df, summary


# ---------------------------------------------------------------------------
# Threshold / quality gate
# ---------------------------------------------------------------------------


def check_threshold(
    summary: ValidationSummary,
    threshold: float = 0.10,
    abort_on_exceed: bool = True,
) -> bool:
    """Check if invalid row percentage exceeds threshold.

    Returns True if within threshold, False if exceeded.
    Raises ValidationError if threshold exceeded and ``abort_on_exceed=True``.
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


# ---------------------------------------------------------------------------
# Threshold normalization
# ---------------------------------------------------------------------------


def _normalize_threshold_value(threshold: float | None) -> float:
    """Normalize the invalid-row threshold used during validation.

    Accepts both fractional values (0.1) and whole percentages (10 for
    10%).
    """
    DEFAULT = 0.10

    # If caller provided an explicit threshold, validate its range.
    if threshold is not None:
        try:
            if not (0.0 <= float(threshold) <= 1.0):
                logger.warning(
                    "Explicit threshold %s out of range [0.0,1.0]; "
                    "using default %.2f",
                    threshold,
                    DEFAULT,
                )
                return DEFAULT
            return float(threshold)
        except Exception:
            logger.warning(
                "Invalid explicit threshold %s; using default %.2f",
                threshold,
                DEFAULT,
            )
            return DEFAULT

    # No explicit threshold: try environment variable, with robust parsing.
    threshold_env = os.getenv("VALIDATION_INVALID_PERCENT_THRESHOLD")
    if threshold_env is None:
        return DEFAULT

    s = threshold_env.strip()
    try:
        # Support values like '10', '0.1', '10%', '  10 % '
        if s.endswith("%"):
            num = float(s[:-1].strip())
            t = num / 100.0
        else:
            t = float(s)
            # Treat numeric values > 1 as whole-percentage (e.g. 10 -> 0.10)
            if t > 1:
                t /= 100.0

        if not (0.0 <= t <= 1.0):
            msg = (
                "Environment variable "
                "VALIDATION_INVALID_PERCENT_THRESHOLD='%s' "
                "parsed to %s which is out of range [0.0,1.0]; "
                "using default %.2f"
            )
            logger.warning(msg, threshold_env, t, DEFAULT)
            return DEFAULT

        return float(t)
    except ValueError:
        msg = (
            "Could not parse "
            "VALIDATION_INVALID_PERCENT_THRESHOLD='%s'; "
            "using default %.2f"
        )
        logger.warning(msg, threshold_env, DEFAULT)
        return DEFAULT
    except Exception as e:
        msg = (
            "Unexpected error parsing "
            "VALIDATION_INVALID_PERCENT_THRESHOLD='%s': %s; "
            "using default %.2f"
        )
        logger.warning(msg, threshold_env, e, DEFAULT)
        return DEFAULT


# ---------------------------------------------------------------------------
# DataFrame coercion
# ---------------------------------------------------------------------------


def _coerce_dataframe_columns(df: pd.DataFrame) -> None:
    """Normalize common DataFrame column types in-place for validation.

    Coerces date, price, and volume columns into consistent datetime,
    numeric, and nullable-integer types expected by validators.
    """
    # Normalize date
    if "date" in df.columns:
        with contextlib.suppress(Exception):
            df["date"] = pd.to_datetime(
                df["date"], utc=True, errors="coerce"
            )
    # Coerce numeric price columns
    numeric_cols = [
        c for c in ("open", "high", "low", "close") if c in df.columns
    ]
    for c in numeric_cols:
        with contextlib.suppress(Exception):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Volume as nullable integer when possible
    if "volume" in df.columns:
        with contextlib.suppress(Exception):
            df["volume"] = pd.to_numeric(
                df["volume"], errors="coerce"
            ).astype("Int64")
