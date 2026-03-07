"""Persistence and logging of invalid rows."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, cast

import pandas as pd

from src.validation.errors import ErrorRecords

logger = logging.getLogger(__name__)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _flatten_invalid_error_records(
    invalid_df: pd.DataFrame,
) -> ErrorRecords:
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
    job_id: str | None = None,
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
            job_id=job_id,
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

    The filename pattern follows: ``raw/<provider>/invalid-<ticker>-<ts>.csv``.
    """
    if invalid_df is None or invalid_df.empty:
        return ""

    folder = dest_folder or (raw_root or "raw")
    folder = os.path.join(folder, provider)
    _ensure_dir(folder)

    filename = f"invalid-{ticker}-{ts}.csv"
    path = os.path.join(folder, filename)

    # Prepare a copy for persistence and strip validation metadata
    df_to_write = invalid_df.copy()
    if "_validation_errors" in df_to_write.columns:
        try:
            df_to_write = df_to_write.drop(columns=["_validation_errors"])
        except Exception as e:  # capture any unexpected failure
            msg = (
                "Could not drop _validation_errors column before persisting "
                "invalid rows for %s/%s: %s"
            )
            # include exception info so we don't silently swallow it
            logger.warning(msg, provider, ticker, e, exc_info=e)

    # Write CSV
    df_to_write.to_csv(path, index=True)

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
    """Append an entry to ``metadata/ingest_logs.jsonl`` (JSON Lines)
    describing invalid rows.

    This implementation appends a single JSON object per line (JSONL),
    which is append-only and serves as the source-of-record for ingest
    events.
    """
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

    # Append as a single JSON object per line (JSONL).
    line = json.dumps(entry, ensure_ascii=False)
    with open(metadata_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass

    return entry
