"""Raw CSV persistence layer for the ingest pipeline.

Responsible for saving provider DataFrames to disk under ``raw/<provider>/``
with deterministic checksum files, and for appending machine-readable metadata
entries to the JSONL audit log (``metadata/ingest_logs.jsonl``).

Purposely has *no* knowledge of adapter factories, canonical mapping, or
snapshot orchestration — those concerns live in :mod:`src.ingest.pipeline` and
:mod:`src.ingest.snapshot_ingest` respectively.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd

from src.utils.checksums import (  # noqa: F401
    serialize_df_bytes,
    sha256_bytes,
    sha256_file,
)

logger = logging.getLogger(__name__)

# Default paths — kept here so callers that import only this module don't need
# to also import pipeline.py.
DEFAULT_DB = Path("dados/data.db")
DEFAULT_METADATA = Path("metadata/ingest_logs.jsonl")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


# helper `_db_initialized` removed: list file existed but was unused.
# (previous story comments noted optional DB checks; these belong in
# `scripts/init_ingest_db.py` or the orchestration layer, not raw storage.)
# the implementation was deleted entirely during a refactor, but the
# comment accidentally left behind a few stray lines.  They have been
# removed here for clarity.


def _ensure_metadata_file(metadata_path: Union[str, Path]) -> None:
    """Ensure the metadata directory exists and the JSONL file is initialised.

    Creates an empty file atomically (write-to-tmp then ``os.replace``) if the
    target does not exist yet.  Does not modify existing content.
    """
    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    if not metadata_path.exists():
        tmp = metadata_path.with_suffix(".tmp")
        tmp.write_text("")
        os.replace(str(tmp), str(metadata_path))


def _log_metadata_error(
    msg: str, e_meta: Exception, metadata: Dict[str, Any]
) -> None:
    """Log a metadata write failure and annotate *metadata* in-place."""
    logger.exception("%s: %s", msg, e_meta)
    metadata["metadata_recorded"] = False
    metadata["metadata_error_message"] = str(e_meta)


def _persist_metadata(
    metadata: Dict[str, Any],
    metadata_path: Union[str, Path] = DEFAULT_METADATA,
) -> None:
    """Atomically append a single JSON object line to the JSONL audit log."""
    _ensure_metadata_file(metadata_path)
    metadata_path = Path(metadata_path)

    line = json.dumps(metadata, ensure_ascii=False)
    with open(metadata_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError as exc:
            # Not critical on some platforms — best-effort.
            logger.warning("fsync failed for metadata path %s: %s", metadata_path, exc)
    metadata["metadata_recorded"] = True
    metadata["metadata_path"] = str(metadata_path)


def _write_csv_atomic(df: pd.DataFrame, file_path: Union[str, Path]) -> None:
    """Write *df* to *file_path* atomically using a sibling temp file."""
    file_path = Path(file_path)
    fd, tmp = tempfile.mkstemp(prefix=f"{file_path.name}.", dir=str(file_path.parent))
    os.close(fd)
    tmp = Path(tmp)
    try:
        df.to_csv(tmp, index=False)
        os.replace(str(tmp), str(file_path))
    finally:
        if tmp.exists() and tmp != file_path:
            with contextlib.suppress(Exception):
                tmp.unlink()


def _write_bytes_atomic(file_path: Union[str, Path], data: bytes) -> None:
    """Write *data* bytes to *file_path* atomically using a sibling temp file."""
    file_path = Path(file_path)
    fd, tmp = tempfile.mkstemp(prefix=f"{file_path.name}.", dir=str(file_path.parent))
    os.close(fd)
    tmp = Path(tmp)
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(str(tmp), str(file_path))
    finally:
        if tmp.exists() and tmp != file_path:
            with contextlib.suppress(Exception):
                tmp.unlink()


def _write_checksum(file_path: Union[str, Path]) -> str:
    """Compute SHA256 of *file_path* and write a sibling ``.checksum`` file.

    The checksum file is written atomically by first creating a temporary
    sibling in the same directory, flushing/fsyncing the contents, and then
    renaming it into place.  This prevents partially-written checksum files
    from appearing if the process is interrupted.
    """
    file_path = Path(file_path)
    checksum = sha256_file(file_path)

    checksum_path = Path(f"{file_path}.checksum")
    # write to temporary sibling in same directory for atomic replace
    fd, tmp = tempfile.mkstemp(
        prefix=f"{checksum_path.name}.",
        dir=str(checksum_path.parent),
    )
    os.close(fd)
    tmp = Path(tmp)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(checksum)
            fh.flush()
            with contextlib.suppress(OSError):
                os.fsync(fh.fileno())
        os.replace(str(tmp), str(checksum_path))
    finally:
        if tmp.exists() and tmp != checksum_path:
            with contextlib.suppress(Exception):
                tmp.unlink()
    return checksum


def _apply_posix_permissions(paths: list[Union[str, Path]]) -> None:
    """Set 0o600 permissions on each path (best-effort, logs on failure)."""
    try:
        if hasattr(os, "chmod"):
            for p in paths:
                os.chmod(str(p), 0o600)
    except Exception:
        logger.exception("Failed to apply permissions to files")


# ---------------------------------------------------------------------------
# Metadata recording helper (used by orchestration layer)
# ---------------------------------------------------------------------------


def record_ingest_metadata(metadata: Dict[str, Any]) -> None:
    """Append an ingest metadata entry to the default JSONL log.

    Best-effort: failures are logged but *never* re-raised so that a metadata
    write failure does not abort a successful data ingestion.
    """
    try:
        _persist_metadata(metadata, DEFAULT_METADATA)
    except Exception as exc:  # pragma: no cover - best-effort
        logger.exception("failed to record ingest metadata: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_raw_csv(
    df: pd.DataFrame,
    provider: str,
    ticker: str,
    ts: Optional[Union[str, datetime]] = None,
    raw_root: Union[str, Path] = Path("raw"),
    db_path: Union[str, Path] = DEFAULT_DB,
    metadata_path: Union[str, Path] = DEFAULT_METADATA,
    set_permissions: bool = False,
) -> Dict[str, Any]:
    """Save *df* to ``raw/<provider>/<ticker>-<ts>.csv`` and register metadata.

    Writes the CSV atomically (temp-file + ``os.replace``), computes a
    deterministic SHA256 checksum, and appends a metadata record to the JSONL
    audit log.  Database initialization is **not** performed here — use
    ``scripts/init_ingest_db.py`` before expecting DB metadata entries.

    Parameters
    ----------
    df:
        DataFrame to persist.  Columns will be sorted for a stable byte
        representation.
    provider:
        Provider name used as the sub-directory under *raw_root*.
    ticker:
        Ticker symbol included in the filename.
    ts:
        UTC timestamp string (``YYYYMMDDTHHMMSSz``) or :class:`datetime`.
        Defaults to ``datetime.now(UTC)``.
    raw_root:
        Root directory for raw files.  Defaults to ``raw/``.
    db_path:
        Legacy parameter retained for compatibility — no longer used
        internally.

        .. deprecated:: 0.1.0
            The ``db_path`` argument has no effect and will be removed in a
            future release.  Passing a non-default value will raise a
            :class:`DeprecationWarning` at runtime so callers can update
            their code before the parameter is removed entirely.
    metadata_path:
        Path to the JSONL audit log.
    set_permissions:
        When ``True`` chmod the written files to ``0o600``.

    Returns
    -------
    dict
        Metadata dict with keys: ``job_id``, ``source``, ``fetched_at``,
        ``raw_checksum``, ``rows``, ``filepath``, ``status``.
    """
    # db_path is a no-op; warn when callers provide a non-default value.
    # convert to Path first to avoid spurious warnings when a str is passed.
    if Path(db_path) != DEFAULT_DB:
        import warnings

        warnings.warn(
            "The db_path parameter to save_raw_csv is deprecated and has no effect; "
            "it will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )

    if ts is None:
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    elif isinstance(ts, datetime):
        ts_str = ts.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    else:
        ts_str = str(ts)

    raw_root = Path(raw_root)
    provider_dir = raw_root / provider
    provider_dir.mkdir(parents=True, exist_ok=True)

    # Stable column order for deterministic checksum
    try:
        df_to_save = df.reindex(sorted(df.columns), axis=1)
    except Exception:
        df_to_save = df.copy()

    file_path = provider_dir / f"{ticker}-{ts_str}.csv"
    job_id = str(uuid.uuid4())
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = len(df_to_save)

    try:
        df_bytes = serialize_df_bytes(
            df_to_save,
            index=True,
            date_format="%Y-%m-%dT%H:%M:%S",
            float_format="%.10g",
            na_rep="",
        )
        _write_bytes_atomic(file_path, df_bytes)
        # use helper which writes checksum atomically (temp file + replace)
        checksum = _write_checksum(file_path)

        if set_permissions:
            _apply_posix_permissions([file_path, Path(f"{file_path}.checksum")])

        metadata: Dict[str, Any] = {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": checksum,
            "rows": rows,
            "filepath": str(file_path),
            "status": "success",
            "created_at": fetched_at,
        }
        try:
            _persist_metadata(metadata, metadata_path)
        except Exception as e_meta:
            _log_metadata_error("Failed to write metadata to JSON", e_meta, metadata)
        return metadata

    except Exception as e:
        logger.exception("Error saving raw CSV: %s", e)
        metadata = {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": None,
            "rows": rows,
            "filepath": str(file_path),
            "status": "error",
            "error_message": str(e),
            "created_at": fetched_at,
            "metadata_recorded": False,
        }
        try:
            _persist_metadata(metadata, metadata_path)
        except Exception as e_meta:
            _log_metadata_error(
                "Failed to write error metadata to JSON", e_meta, metadata
            )
        return metadata
