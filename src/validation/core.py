"""Validação central: verificação de esquema, extração de erros, limiar e coerção."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, cast

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
    """Extrai linhas inválidas e detalhes de erro a partir de SchemaErrors.

    Args:
        df: DataFrame original sendo validado
        schema_errors: exceção SchemaErrors lançada pelo pandera

    Returns:
        Tupla (invalid_df, error_records)
    """
    error_records: ErrorRecords = []
    invalid_indices: set = set()

    # Tenta analisar pandera failure_cases se disponível
    if (
        hasattr(schema_errors, "failure_cases")
        and schema_errors.failure_cases is not None
    ):
        failure_cases = schema_errors.failure_cases
        parsed_indices, parsed_records = _parse_failure_cases(failure_cases)
        if parsed_indices:
            invalid_indices.update(parsed_indices)
            error_records.extend(parsed_records)

    # Se ainda não houver índices, executa heurísticas (ex.: restrição high/low)
    if not invalid_indices:
        h_indices, h_records = _heuristic_high_low_violations(df)
        if h_indices:
            invalid_indices.update(h_indices)
            error_records.extend(h_records)

    # Se ainda nada, registra um único erro de nível de esquema
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

    # Constrói invalid_df a partir dos índices coletados e retorna
    invalid_df = (
        df.loc[list(invalid_indices)].copy()
        if invalid_indices
        else pd.DataFrame()
    )

    return invalid_df, error_records


def _parse_failure_cases(
    failure_cases: pd.DataFrame,
) -> Tuple[IndexSet, ErrorRecords]:
    """Analisa o DataFrame ``failure_cases`` gerado pelo pandera em índices e registros."""
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
    """Detecta violações de restrição high/low e retorna índices + registros."""
    invalid_indices: set = set()
    error_records: List[Dict[str, Any]] = []
    try:
        if "high" in df.columns and "low" in df.columns:
                # marca violações apenas quando ambos os valores estiverem presentes _e_
                # high is strictly less than low; equality is permitted.
                mask_violation = (
                    df["high"].notna()
                    & df["low"].notna()
                    & (df["high"] < df["low"])
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
                                    "Constraint failed: high < low"
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
    """Normaliza exceções SchemaErrors ou SchemaError do pandera em (invalid_df, error_records).

    Centraliza a lógica usada por ``validate_dataframe`` para manter a
    complexidade reduzida.
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
                    except (ValueError, TypeError) as e:
                        # conversão falhou, preserva valor original e registra
                        logger.debug(
                            "não foi possível converter índice %r para int: %s",
                            idx,
                            e,
                        )
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
    df: pd.DataFrame, schema: Optional[type] = None, lazy: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, ValidationSummary]:
    """Valida um DataFrame contra o esquema canônico e separa linhas válidas e inválidas.

    Args:
        df: DataFrame a ser validado (deve estar no formato canônico)
        schema: esquema Pandera a ser usado (padrão: CanonicalSchema)
        lazy: se True, coleta todos os erros antes de lançar exceção (padrão: True)

    Returns:
        Tupla (valid_df, invalid_df, summary)
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

    except SchemaError as e:
        logger.warning(
            "Schema validation failed with SchemaError: %s",
            str(e)[:200],
        )
        invalid_df, error_records = _process_schema_exception(df, e)

    except SchemaError as e:
        logger.warning(
            "Schema validation failed with SchemaError: %s",
            str(e)[:200],
        )
        invalid_df, error_records = _process_schema_exception(df, e)

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
        invalid_df["_validation_errors"] = [
            errors_by_row.get(idx, []) for idx in invalid_df.index
        ]

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
    """Verifica se a porcentagem de linhas inválidas ultrapassa o limiar.

    Retorna True se dentro do limiar, False se excedido.
    Lança ValidationError se exceder e ``abort_on_exceed=True``.
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


def _normalize_threshold_value(
    threshold: float | str | None,
    *,
    source: str = "env",
    default: float = 0.10,
) -> float:
    """Normalize the invalid-row threshold used during validation.

    Accepts both fractional values (0.1) and whole percentages (10 for 10%).

    Behavior differs by *source*:

    - For explicit arguments (source="arg"):
      - Return a float in [0.0, 1.0].
      - Raise ValueError on invalid input so misconfigurations fail loudly.
    - For environment / config (other sources):
      - On invalid input, log a warning and fall back to *default*.
      - Warnings include the normalized threshold value when possible.
    """

    def _coerce_to_float(raw: float | str | None) -> float:
        if raw is None:
            raise ValueError("threshold value is None")
        # allow percentage strings like "10%" transparently
        if isinstance(raw, str) and raw.strip().endswith("%"):
            raw = raw.strip()[:-1].strip()
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"threshold value {raw!r} is not a valid float") from exc

    def _finalize(raw_value: float, strict: bool, source: str, default: float) -> float:
        # convert percentage-style input
        normalized = raw_value / 100.0 if raw_value > 1.0 else raw_value
        if not (0.0 <= normalized <= 1.0):
            if strict:
                raise ValueError(
                    f"Explicit threshold {threshold!r} from {source} "
                    f"normalizes to {normalized:.4f}, which is outside [0.0, 1.0]"
                )
            logger.warning(
                "Threshold %r from %s normalizes to %.4f, which is outside [0.0, 1.0]; "
                "using default %.4f",
                threshold,
                source,
                normalized,
                default,
            )
            return default
        if not strict and normalized != raw_value:
            logger.warning(
                "Threshold %r from %s normalized to %.4f",
                threshold,
                source,
                normalized,
            )
        return normalized

    strict = source == "arg"

    if threshold is None:
        if strict:
            raise ValueError("Explicit threshold must not be None")
        logger.warning(
            "No threshold provided from %s; using default %.4f",
            source,
            default,
        )
        return default

    try:
        raw_value = _coerce_to_float(threshold)
    except ValueError as exc:
        if strict:
            raise
        logger.warning(
            "Invalid threshold %r from %s (%s); using default %.4f",
            threshold,
            source,
            exc,
            default,
        )
        return default

    return _finalize(raw_value, strict, source, default)


# ---------------------------------------------------------------------------
# DataFrame coercion
# ---------------------------------------------------------------------------


def _coerce_dataframe_columns(df: pd.DataFrame) -> None:
    """Normaliza em memória os tipos de colunas comuns do DataFrame para validação.

    Coerce colunas de data, preço e volume em tipos datetime, numérico e
    inteiro anulável consistentes esperados pelos validadores.
    """
    # Normalize date
    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(
                df["date"], utc=True, errors="coerce"
            )
        except (ValueError, TypeError, OverflowError) as exc:
            logger.debug(
                "failed to coerce 'date' column to datetime: %s", exc
            )
    # Coerce numeric price columns
    numeric_cols = [
        c for c in ("open", "high", "low", "close") if c in df.columns
    ]
    for c in numeric_cols:
        try:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        except (ValueError, TypeError, OverflowError) as exc:
            logger.debug(
                "failed to coerce '%s' column to numeric: %s", c, exc
            )
    # Volume as nullable integer when possible
    if "volume" in df.columns:
        try:
            df["volume"] = pd.to_numeric(
                df["volume"], errors="coerce"
            ).astype("Int64")
        except (ValueError, TypeError, OverflowError) as exc:
            logger.debug(
                "failed to coerce 'volume' column to Int64: %s", exc
            )
