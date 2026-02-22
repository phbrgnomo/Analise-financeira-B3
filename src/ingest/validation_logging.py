"""
Logging de rows inválidas para auditoria e debugging do pipeline de ingestão.

Persiste informações detalhadas sobre rows que falharam na validação,
incluindo reason codes, mensagens de erro, e referências aos arquivos raw.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from src.utils.checksums import serialize_df_bytes, sha256_bytes

logger = logging.getLogger(__name__)

DEFAULT_INVALID_LOGS = Path("metadata/ingest_logs.json")
DEFAULT_INVALID_DIR = Path("raw")


def _ensure_metadata_file(metadata_path: Union[str, Path]) -> None:
    """Ensure metadata directory exists and file is initialized as JSON array."""
    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    if not metadata_path.exists():
        tmp = metadata_path.with_suffix(".json.tmp")
        tmp.write_text("[]")
        os.replace(str(tmp), str(metadata_path))


def log_invalid_rows(
    invalid_df: pd.DataFrame,
    ticker: str,
    source: str,
    raw_file: Optional[str] = None,
    job_id: Optional[str] = None,
    metadata_path: Union[str, Path] = DEFAULT_INVALID_LOGS,
) -> List[Dict[str, Any]]:
    """Log invalid rows to metadata file with detailed error information.

    Args:
        invalid_df: DataFrame with invalid rows (should have _validation_errors column)
        ticker: Ticker symbol
        source: Data source/provider name
        raw_file: Path to raw CSV file (optional)
        job_id: Job ID for tracking (generated if not provided)
        metadata_path: Path to metadata JSON file

    Returns:
        List of log entries that were written
    """
    if invalid_df.empty:
        return []

    if job_id is None:
        job_id = str(uuid.uuid4())

    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    log_entries = []

    # Extract validation errors from DataFrame if available
    has_errors = "_validation_errors" in invalid_df.columns
    for idx, row in invalid_df.iterrows():
        entries = _build_log_entries_for_row(
            idx, row, has_errors, ticker, source, raw_file, job_id, created_at
        )
        log_entries.extend(entries)

    # Persist to metadata file
    try:
        _ensure_metadata_file(metadata_path)
        metadata_path = Path(metadata_path)

        # Read existing entries
        try:
            existing = json.loads(metadata_path.read_text())
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

        # Append new entries
        existing.extend(log_entries)

        # Write atomically
        tmp = metadata_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
        os.replace(str(tmp), str(metadata_path))

        logger.info(
            "Logged %d invalid row errors for %s to %s",
            len(log_entries),
            ticker,
            metadata_path,
        )

    except Exception as e:
        logger.exception(f"Failed to log invalid rows to {metadata_path}: {e}")
        # Don't raise - logging failure shouldn't stop the pipeline

    return log_entries


def _build_log_entries_for_row(
    idx,
    row,
    has_errors: bool,
    ticker: str,
    source: str,
    raw_file: Optional[str],
    job_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    """Return list of log entry dicts for a single DataFrame row."""
    if has_errors:
        errors = row["_validation_errors"]
        if not isinstance(errors, list):
            errors = [
                {
                    "reason_code": "VALIDATION_ERROR",
                    "reason_message": "Unknown error",
                }
            ]
    else:
        errors = [
            {
                "reason_code": "VALIDATION_ERROR",
                "reason_message": "Validation failed",
            }
        ]

    out: List[Dict[str, Any]] = []
    for error in errors:
        try:
            row_index = int(idx)  # type: ignore[arg-type]
        except Exception:
            row_index = str(idx)

        entry = {
            "job_id": job_id,
            "ticker": ticker,
            "source": source,
            "raw_file": raw_file,
            "row_index": row_index,
            "column": error.get("column"),
            "reason_code": error.get("reason_code", "VALIDATION_ERROR"),
            "reason_message": error.get("reason_message", "Validation failed"),
            "failure_value": str(error.get("failure_value"))
            if error.get("failure_value") is not None
            else None,
            "created_at": created_at,
        }
        out.append(entry)

    return out


def save_invalid_rows(
    invalid_df: pd.DataFrame,
    ticker: str,
    provider: str,
    raw_root: Union[str, Path] = DEFAULT_INVALID_DIR,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Save invalid rows to CSV file with checksum.

    Args:
        invalid_df: DataFrame with invalid rows
        ticker: Ticker symbol
        provider: Data provider name
        raw_root: Root directory for raw files
        ts: Timestamp string (generated if not provided)

    Returns:
        Dict with metadata about saved file (filepath, checksum, etc.)
    """
    if invalid_df.empty:
        return {
            "filepath": None,
            "checksum": None,
            "rows": 0,
            "status": "skipped_empty",
        }

    if ts is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raw_root = Path(raw_root)
    provider_dir = raw_root / provider / "invalid"
    provider_dir.mkdir(parents=True, exist_ok=True)

    filename = f"invalid-{ticker}-{ts}.csv"
    file_path = provider_dir / filename

    # Remove internal validation metadata before saving
    df_to_save = invalid_df.copy()
    if "_validation_errors" in df_to_save.columns:
        df_to_save = df_to_save.drop(columns=["_validation_errors"])

    try:
        return _write_invalid_rows_with_checksum(
            df_to_save, file_path, invalid_df, ticker
        )
    except Exception as e:
        logger.exception(f"Failed to save invalid rows to {file_path}: {e}")
        return {
            "filepath": str(file_path),
            "checksum": None,
            "rows": len(invalid_df),
            "status": "error",
            "error_message": str(e),
        }


def _write_invalid_rows_with_checksum(df_to_save, file_path, invalid_df, ticker):
    """Persist invalid rows to a CSV file and generate a checksum sidecar.

    This helper writes a deterministic CSV representation of invalid rows,
    computes its checksum, and returns metadata about the persisted artifact.

    Args:
        df_to_save: DataFrame containing the invalid rows to be persisted.
        file_path: Target path where the CSV file will be written.
        invalid_df: Original invalid-rows DataFrame, used for row-count metadata.
        ticker: Ticker symbol associated with the invalid rows.

    Returns:
        Dict with metadata about the saved file, including filepath, checksum,
        number of rows, and a status string.
    """
    # Serialize deterministically
    df_bytes = serialize_df_bytes(
        df_to_save,
        index=True,
        date_format="%Y-%m-%dT%H:%M:%S",
        float_format="%.10g",
        na_rep="",
    )

    # Write file
    with open(file_path, "wb") as f:
        f.write(df_bytes)

    # Compute checksum
    checksum = sha256_bytes(df_bytes)

    # Write checksum file
    checksum_path = Path(f"{str(file_path)}.checksum")
    checksum_path.write_text(checksum)

    logger.info(f"Saved {len(invalid_df)} invalid rows for {ticker} to {file_path}")

    return {
        "filepath": str(file_path),
        "checksum": checksum,
        "rows": len(invalid_df),
        "status": "success",
    }
