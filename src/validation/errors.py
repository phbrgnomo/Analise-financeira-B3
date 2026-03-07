"""Error categorization, type aliases, and exceptions for validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Set

# Type aliases for common shapes used across the validation package
ErrorRecord = Dict[str, Any]
ErrorRecords = List[ErrorRecord]
IndexSet = Set[Any]


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
