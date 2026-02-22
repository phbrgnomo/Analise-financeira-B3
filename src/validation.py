"""
Módulo de validação de DataFrames contra schema canônico.

Fornece validação de DataFrames, flagging de rows inválidas, e logging estruturado
de erros de validação para auditoria e debugging do pipeline de ingestão.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Set, Tuple, cast

import numpy as np
import pandas as pd
from pandera.errors import SchemaError, SchemaErrors

from src.etl.mapper import CanonicalSchema

# Type aliases for common shapes used across this module
ErrorRecord = Dict[str, Any]
ErrorRecords = List[ErrorRecord]
IndexSet = Set[Any]


logger = logging.getLogger(__name__)


@dataclass
class ValidationSummary:
    """Resumo dos resultados de validação do DataFrame."""

    rows_total: int
    rows_valid: int
    rows_invalid: int
    invalid_percent: float
    error_codes_count: Dict[str, int]


class ValidationError(Exception):
    """Exceção lançada quando o limite de validação é excedido."""


def _categorize_error(
    error_msg: str,
    column: str | None = None,
    *,
    error_lower: str | None = None,
) -> str:
    """Map pandera error messages to human-readable reason codes.

    This function delegates to a module-level cached categorizer and small
    helper predicates to keep cyclomatic complexity low and make unit
    testing easier.
    """

    if error_lower is None:
        error_lower = error_msg.lower()

    return _cached_categorize(error_lower, column)


def _is_missing_col(el: str) -> bool:
    return "column" in el and ("not in" in el or "missing" in el)


def _column_specific_code(el: str, col: str | None) -> str | None:
    if not col:
        return None
    col_lower = col.lower()
    if (col_lower == "date" or "date" in col_lower) and (
        "type" in el or "datetime" in el
    ):
        return "BAD_DATE"
    if col_lower in {"open", "high", "low", "close"} and (
        "float" in el or "numeric" in el
    ):
        return "NON_NUMERIC_PRICE"
    if col_lower == "volume":
        if "negative" in el or "< 0" in el:
            return "NEGATIVE_VOLUME"
        if "int" in el or "numeric" in el:
            return "NON_NUMERIC_VOLUME"
    return None


def _generic_code(el: str) -> str | None:
    if "float" in el or "int" in el or "coerce" in el:
        return "TYPE_ERROR"
    return "CONSTRAINT_VIOLATION" if "check" in el or "constraint" in el else None


@lru_cache(maxsize=1024)
def _cached_categorize(el: str, col: str | None) -> str:
    if _is_missing_col(el):
        return "MISSING_COL"

    if col_code := _column_specific_code(el, col):
        return col_code

    generic = _generic_code(el)
    return generic or "VALIDATION_ERROR"


def _extract_invalid_rows_from_schema_errors(
    df: pd.DataFrame, schema_errors: SchemaErrors
) -> Tuple[pd.DataFrame, ErrorRecords]:
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
        # Determine reason and choose fallback behavior:
        # - If it's a missing-column error, mark all rows invalid (legacy
        #   behaviour relied on by tests and callers).
        # - Otherwise emit a single schema-level error record so we don't
        #   noisily mark every row invalid for higher-level schema problems.
        error_msg = str(schema_errors)
        reason_code = _categorize_error(error_msg)

        # Avoid marking all rows invalid as a heuristic fallback — this can
        # obscure schema-level issues. Emit a single schema-level error
        # record instead so callers can decide how to treat it. If callers
        # explicitly need per-row marking for missing columns, they should
        # handle that at a higher level.
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
        df.loc[list(invalid_indices)].copy() if invalid_indices else pd.DataFrame()
    )

    return invalid_df, error_records


def _parse_failure_cases(failure_cases) -> Tuple[IndexSet, ErrorRecords]:
    """Parse `failure_cases` DataFrame emitted by pandera into indices and records."""
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
    invalid_indices = set()
    error_records: List[Dict[str, Any]] = []
    try:
        if "high" in df.columns and "low" in df.columns:
            mask_violation = ~(
                df["high"].isna() | df["low"].isna() | (df["high"] > df["low"])
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
    except Exception as exc:
        # Registrar falhas do heurístico para facilitar o diagnóstico,
        # retornando vazio como fallback resiliente.
        logger.debug("Heuristic high/low check failed: %s", exc, exc_info=True)
        return set(), []

    return invalid_indices, error_records


def _process_schema_exception(
    df: pd.DataFrame, exc: Exception
) -> Tuple[pd.DataFrame, ErrorRecords]:
    """Normalize pandera SchemaErrors or SchemaError into (invalid_df, error_records).

    This centralizes the logic used by `validate_dataframe` to keep complexity low.
    """
    # SchemaErrors (multiple failure_cases) or SchemaError (single) are both
    # handled here and return a consistent pair.
    if isinstance(exc, SchemaErrors):
        invalid_df, error_records = _extract_invalid_rows_from_schema_errors(df, exc)

        # If failure_cases didn't provide row indices but the error is a
        # missing-column type, mark all rows invalid (legacy behaviour).
        if invalid_df.empty:
            reason_code = _categorize_error(str(exc))
            if reason_code == "MISSING_COL":
                error_records = []
                error_records.extend(
                    {
                        "row_index": idx,
                        "column": None,
                        "reason_code": reason_code,
                        "reason_message": str(exc)[:200],
                        "failure_value": None,
                    }
                    for idx in df.index
                )
                invalid_df = df.copy()

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
        logger.warning("Schema validation failed with SchemaErrors: %s", str(e)[:200])
        invalid_df, error_records = _process_schema_exception(df, e)
        valid_df = df.copy() if invalid_df.empty else df.drop(index=invalid_df.index)

    except SchemaError as e:
        logger.warning("Schema validation failed with SchemaError: %s", str(e)[:200])
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
    """Normalize the invalid-row threshold used during validation.

    This helper derives an effective threshold from an explicit value,
    an environment variable, or a default fallback, and accepts both
    fractional values (0.1) and whole percentages (10 for 10%).

    Args:
        threshold: Optional threshold as a fraction (0.0-1.0). If None,
            the value is read from the environment variable
            VALIDATION_INVALID_PERCENT_THRESHOLD or defaults to 0.10.

    Returns:
        A normalized threshold as a float fraction between 0.0 and 1.0.
    """
    import os

    DEFAULT = 0.10

    # If caller provided an explicit threshold, validate its range.
    if threshold is not None:
        try:
            if not (0.0 <= float(threshold) <= 1.0):
                logger.warning(
                    "Explicit threshold %s out of range [0.0,1.0]; using default %.2f",
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
                "Environment variable VALIDATION_INVALID_PERCENT_THRESHOLD='%s' "
                "parsed to %s which is out of range [0.0,1.0]; using default %.2f"
            )
            logger.warning(msg, threshold_env, t, DEFAULT)
            return DEFAULT

        return float(t)
    except ValueError:
        msg = (
            "Could not parse VALIDATION_INVALID_PERCENT_THRESHOLD='%s'; "
            "using default %.2f"
        )
        logger.warning(msg, threshold_env, DEFAULT)
        return DEFAULT
    except Exception as e:
        msg = (
            "Unexpected error parsing VALIDATION_INVALID_PERCENT_THRESHOLD='%s': %s; "
            "using default %.2f"
        )
        logger.warning(msg, threshold_env, e, DEFAULT)
        return DEFAULT


def _coerce_dataframe_columns(df: pd.DataFrame) -> None:
    """Normalize common DataFrame column types in-place for validation.

    This helper coerces date, price, and volume columns into consistent
    datetime, numeric, and nullable-integer types expected by validators.

    Args:
        df: DataFrame to normalize, modified in-place.
    """
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


def _flatten_invalid_error_records(invalid_df: pd.DataFrame) -> ErrorRecords:
    details: ErrorRecords = []
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

    # Prepare a copy for persistence and strip validation metadata so
    # we don't persist internal `_validation_errors` structures.
    df_to_write = invalid_df.copy()
    if "_validation_errors" in df_to_write.columns:
        try:
            df_to_write = df_to_write.drop(columns=["_validation_errors"])
        except Exception:
            # If dropping fails for any reason, fall back to original copy
            # but log so we can investigate.
            msg = (
                "Could not drop _validation_errors column before persisting "
                "invalid rows for %s/%s"
            )
            logger.warning(msg, provider, ticker)

    # Write CSV
    df_to_write.to_csv(path, index=True)

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
    from datetime import datetime, timezone

    entry = {
        "job_id": job_id or "",
        "provider": provider,
        "ticker": ticker,
        "raw_file": raw_file,
        "invalid_filepath": invalid_filepath,
        "invalid_count": len(error_records) if error_records else 0,
        "error_details": error_records,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if meta_dir := os.path.dirname(metadata_path):
        _ensure_dir(meta_dir)

    # Append entry atomically using JSON Lines (one JSON object per line).
    # This avoids read/modify/write races when multiple processes append
    # concurrently. If append fails for any reason, fall back to the
    # legacy read/modify/write with an atomic replace.
    try:
        with open(metadata_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Fallback: try legacy array write using a temp file + replace
        data = []
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh) or []
            except Exception:
                data = []

        data.append(entry)
        tmp_path = metadata_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        try:
            os.replace(tmp_path, metadata_path)
        except Exception:
            # If atomic replace fails, attempt a plain write as last resort
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
    check_threshold(summary, threshold=threshold, abort_on_exceed=abort_on_exceed)

    return valid_df, invalid_df, summary, details
