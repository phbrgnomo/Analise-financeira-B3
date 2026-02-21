"""
Módulo de validação de DataFrames contra schema canônico.

Fornece validação de DataFrames, flagging de rows inválidas, e logging estruturado
de erros de validação para auditoria e debugging do pipeline de ingestão.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

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


def _categorize_error(error_msg: str, column: str = None) -> str:
    """Map pandera error messages to human-readable reason codes.
    
    Args:
        error_msg: Error message from pandera
        column: Column name where error occurred (if known)
        
    Returns:
        Reason code string (e.g., 'MISSING_COL', 'BAD_DATE', 'NON_NUMERIC_PRICE')
    """
    error_lower = error_msg.lower()
    
    # Handle missing column errors
    if "column" in error_lower and ("not in" in error_lower or "missing" in error_lower):
        return "MISSING_COL"
    
    # Handle type errors by column name and error content
    if column:
        col_lower = column.lower()
        if col_lower == "date" or "date" in col_lower:
            if "type" in error_lower or "datetime" in error_lower:
                return "BAD_DATE"
        if col_lower in ("open", "high", "low", "close"):
            if "float" in error_lower or "numeric" in error_lower:
                return "NON_NUMERIC_PRICE"
        if col_lower == "volume":
            if "negative" in error_lower or "< 0" in error_lower:
                return "NEGATIVE_VOLUME"
            if "int" in error_lower or "numeric" in error_lower:
                return "NON_NUMERIC_VOLUME"
    
    # Generic type errors
    if "float" in error_lower or "int" in error_lower:
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
    
    # Extract failure cases from schema_errors.failure_cases DataFrame
    if hasattr(schema_errors, 'failure_cases') and schema_errors.failure_cases is not None:
        failure_cases = schema_errors.failure_cases
        
        for _, row in failure_cases.iterrows():
            index = row.get('index')
            column = row.get('column')
            check = row.get('check')
            failure_case = row.get('failure_case')
            
            # Build error message
            error_msg = f"Column '{column}' failed check: {check}"
            reason_code = _categorize_error(str(check), column)
            
            if index is not None:
                invalid_indices.add(index)
                error_records.append({
                    'row_index': index,
                    'column': column,
                    'reason_code': reason_code,
                    'reason_message': error_msg,
                    'failure_value': failure_case,
                })
    
    # If no specific row indices found, mark all rows as potentially invalid
    # (happens with structural errors like missing columns)
    if not invalid_indices:
        error_msg = str(schema_errors)
        reason_code = _categorize_error(error_msg)
        for idx in df.index:
            invalid_indices.add(idx)
            error_records.append({
                'row_index': idx,
                'column': None,
                'reason_code': reason_code,
                'reason_message': error_msg[:200],  # Truncate long messages
                'failure_value': None,
            })
    
    # Extract invalid rows
    invalid_df = df.loc[list(invalid_indices)].copy() if invalid_indices else pd.DataFrame()
    
    return invalid_df, error_records


def validate_dataframe(
    df: pd.DataFrame,
    schema=None,
    lazy: bool = True
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
            error_codes_count={}
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
            error_codes_count={}
        )
        return valid_df, pd.DataFrame(), summary
        
    except SchemaError as e:
        # Some rows are invalid - extract them
        logger.warning(f"Schema validation failed with {type(e).__name__}: {str(e)[:200]}")
        
        # Try to extract detailed error information
        if isinstance(e, SchemaErrors):
            invalid_df, error_records = _extract_invalid_rows_from_schema_errors(df, e)
        else:
            # Single SchemaError - less detailed info available
            error_msg = str(e)
            reason_code = _categorize_error(error_msg)
            error_records = [{
                'row_index': idx,
                'column': None,
                'reason_code': reason_code,
                'reason_message': error_msg[:200],
                'failure_value': None,
            } for idx in df.index]
            invalid_df = df.copy()
        
        # Build error metadata for invalid rows
        if not invalid_df.empty:
            # Aggregate errors by row index
            errors_by_row = {}
            for rec in error_records:
                idx = rec['row_index']
                if idx not in errors_by_row:
                    errors_by_row[idx] = []
                errors_by_row[idx].append(rec)
            
            # Add error metadata to invalid_df
            invalid_df = invalid_df.copy()
            invalid_df['_validation_errors'] = invalid_df.index.map(
                lambda idx: errors_by_row.get(idx, [])
            )
        
        # Get valid rows (set difference)
        invalid_indices = set(invalid_df.index)
        valid_indices = [idx for idx in df.index if idx not in invalid_indices]
        valid_df = df.loc[valid_indices].copy() if valid_indices else pd.DataFrame()
        
        # Build summary
        rows_invalid = len(invalid_df)
        rows_valid = len(valid_df)
        invalid_percent = (rows_invalid / rows_total) if rows_total > 0 else 0.0
        
        # Count error codes
        error_codes_count = {}
        for rec in error_records:
            code = rec['reason_code']
            error_codes_count[code] = error_codes_count.get(code, 0) + 1
        
        summary = ValidationSummary(
            rows_total=rows_total,
            rows_valid=rows_valid,
            rows_invalid=rows_invalid,
            invalid_percent=invalid_percent,
            error_codes_count=error_codes_count
        )
        
        logger.info(
            f"Validation complete: {rows_valid}/{rows_total} valid "
            f"({invalid_percent:.1%} invalid). Error codes: {error_codes_count}"
        )
        
        return valid_df, invalid_df, summary


def check_threshold(
    summary: ValidationSummary,
    threshold: float = 0.10,
    abort_on_exceed: bool = True
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
            f"Validation threshold exceeded: {summary.invalid_percent:.1%} invalid rows "
            f"(threshold: {threshold:.1%}). "
            f"{summary.rows_invalid}/{summary.rows_total} rows invalid. "
            f"Error codes: {summary.error_codes_count}"
        )
        logger.error(msg)
        if abort_on_exceed:
            raise ValidationError(msg)
        return False
    
    return True
