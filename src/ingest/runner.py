"""Ingest runner helpers.

Provides a convenience wrapper that enforces validation before writing to the
database. Callers should use this helper to avoid accidentally bypassing
validation.
"""

from typing import Tuple

import pandas as pd

from src import db as src_db
from src.paths import INGEST_LOGS, RAW_ROOT
from src.validation import ValidationSummary, validate_and_handle


def run_write_with_validation(
    df: pd.DataFrame,
    provider: str,
    ticker: str,
    raw_file: str,
    ts: str,
    *,
    raw_root: str = RAW_ROOT,
    metadata_path: str = INGEST_LOGS,
    threshold: float | None = None,
    abort_on_exceed: bool = True,
    persist_invalid: bool = True,
    db_path: str | None = None,
    schema_version: str | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, ValidationSummary, dict]:
    """Validate the DataFrame and write valid rows to DB via `write_prices`.

    Returns the same tuple as `validate_and_handle` but also writes valid rows
    to the DB when validation passes (or when not aborting).
    """
    valid_df, invalid_df, summary, details = validate_and_handle(
        df,
        provider=provider,
        ticker=ticker,
        raw_file=raw_file,
        ts=ts,
        raw_root=raw_root,
        metadata_path=metadata_path,
        threshold=threshold,
        abort_on_exceed=abort_on_exceed,
        persist_invalid=persist_invalid,
    )

    # If there are valid rows, write them to DB using canonical write_prices.
    if not valid_df.empty:
        try:
            src_db.write_prices(
                valid_df, ticker, schema_version=schema_version, db_path=db_path
            )
        except Exception as e:
            # Do not raise to avoid masking validation results; caller may
            # choose to treat write failures separately.
            # Log via DB logger
            src_db._logger.error("Failed to write validated rows to DB: %s", e)

    return valid_df, invalid_df, summary, details
