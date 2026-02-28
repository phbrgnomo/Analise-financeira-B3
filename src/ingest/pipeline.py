"""Ingest pipeline helpers.

Functions to save provider raw responses to CSV and register ingest metadata
in a local SQLite database (dados/data.db) and optional checksum files.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd
import typer  # used by ingest_command error handling

from src.utils.checksums import serialize_df_bytes, sha256_bytes, sha256_file

logger = logging.getLogger(__name__)

# Legacy DB var kept for compatibility; metadata will be written to JSONL
DEFAULT_DB = Path("dados/data.db")
DEFAULT_METADATA = Path("metadata/ingest_logs.jsonl")


# ---------------------------------------------------------------------------
# Story 1.3: basic ingest orchestration and CLI support
# ---------------------------------------------------------------------------

def _record_ingest_metadata(metadata: Dict[str, Any]) -> None:
    """Helper to append ingest-specific metadata entries to the JSONL log.

    This is a small wrapper around :func:`_persist_metadata` that ensures the
    directory exists and that callers don't need to know the default path.
    """
    try:
        _persist_metadata(metadata, DEFAULT_METADATA)
    except Exception as exc:  # pragma: no cover - best-effort logging
        logger.exception("failed to record ingest metadata: %s", exc)


def ingest(
    ticker: str,
    source: str = "yfinance",
    *,
    dry_run: bool = False,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Minimal pipeline orchestration used by CLI and tests.

    This function implements the core behaviour described in Story 1.3:

    * Fetch raw data from a provider adapter via the adapter factory.
    * Map the provider output into the canonical schema.
    * When ``dry_run`` is False, save the raw CSV and attempt to persist
      canonical rows to the database using the existing
      :func:`ingest_from_snapshot` helper (Story 1.6+).  ``force_refresh`` is
      forwarded to that helper.
    * Always generate and return a ``job_id`` so that callers can correlate
      log entries.

    The function returns a dictionary containing a ``job_id`` and
    ``status``.  Errors during fetch, mapping or persistence are caught and
    translated into a result with ``status=='error'`` and an ``error_message``
    so that callers (including the CLI wrapper) can choose an appropriate
    exit code without needing to catch exceptions.  This behaviour makes the
    logic easy to drive from tests or scripting environments while still
    recording useful metadata.
    """
    job_id = str(uuid.uuid4())
    logger.info(
        "pipeline.ingest start",
        extra={
            "job_id": job_id,
            "ticker": ticker,
            "source": source,
            "dry_run": dry_run,
            "force_refresh": force_refresh,
        },
    )

    # fetch
    try:
        from src.adapters.factory import get_adapter

        adapter = get_adapter(source)
        df = adapter.fetch(ticker)
    except Exception as exc:  # fetch failure
        msg = f"adapter.fetch failed: {exc}"
        logger.exception(msg)
        metadata = {
            "job_id": job_id,
            "ticker": ticker,
            "source": source,
            "status": "error",
            "error_message": msg,
        }
        _record_ingest_metadata(metadata)
        return {"job_id": job_id, "status": "error", "error_message": msg}

    # map to canonical
    try:
        from src.etl.mapper import to_canonical

        canonical = to_canonical(df, provider_name=source, ticker=ticker)
    except Exception as exc:  # mapper failure
        msg = f"mapper failed: {exc}"
        logger.exception(msg)
        metadata = {
            "job_id": job_id,
            "ticker": ticker,
            "source": source,
            "status": "error",
            "error_message": msg,
        }
        _record_ingest_metadata(metadata)
        return {"job_id": job_id, "status": "error", "error_message": msg}

    # if the caller only wanted a dry run, return now
    if dry_run:
        logger.info(
            "dry run completed",
            extra={"job_id": job_id, "rows": len(canonical)},
        )
        return {
            "job_id": job_id,
            "status": "success",
            "dry_run": True,
            "rows": len(canonical),
        }

    # persist raw CSV (Story 1.4)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        save_meta = save_raw_csv(df, source, ticker, ts)
    except Exception as exc:
        msg = f"failed to save raw CSV: {exc}"
        logger.exception(msg)
        metadata = {
            "job_id": job_id,
            "ticker": ticker,
            "source": source,
            "status": "error",
            "error_message": msg,
        }
        _record_ingest_metadata(metadata)
        return {"job_id": job_id, "status": "error", "error_message": msg}

    # attempt DB persistence with snapshot helper; the helper already logs its
    # own metadata.  ``ingest_from_snapshot`` is defined later in this module
    # so we can call it directly instead of importing ourselves at runtime.
    persist_result: Dict[str, Any] = {}
    try:
        persist_result = ingest_from_snapshot(canonical, ticker, force=force_refresh)
    except Exception as exc:  # pragma: no cover - just in case
        logger.exception("persistence step failed: %s", exc)
        persist_result = {"status": "error", "error_message": str(exc)}

    # final metadata entry for the orchestrator run
    metadata = {
        "job_id": job_id,
        "ticker": ticker,
        "source": source,
        "status": "success",
        "rows": len(canonical),
        "persist": persist_result,
    }
    _record_ingest_metadata(metadata)

    logger.info(
        "pipeline.ingest completed",
        extra={"job_id": job_id, "rows": len(canonical)},
    )

    return {
        "job_id": job_id,
        "status": "success",
        "save_meta": save_meta,
        "persist": persist_result,
    }


def ingest_command(
    ticker: str,
    source: str = "yfinance",
    dry_run: bool = False,
    force_refresh: bool = False,
) -> int:
    """Typer-friendly wrapper that prints results and returns an exit code.

    Any unhandled exception from :func:`ingest` is caught and turned into a
    non-zero exit code so that the CLI is safe for scripting.  We still
    propagate the exception when running programmatically (e.g. tests can
    assert via ``with pytest.raises``).
    """
    try:
        result = ingest(ticker, source, dry_run=dry_run, force_refresh=force_refresh)
    except Exception as exc:  # pragma: no cover - defensive
        typer.secho(f"fatal error: {exc}", err=True)
        return 1

    job_id = result.get("job_id")
    # successful outcome
    if result.get("status") == "success":
        if job_id:
            print(f"job_id={job_id}")
        if dry_run:
            print("dry run completed; no data written")
        return 0

    # failure path: log to stderr so stdout remains parsable
    err = result.get("error_message", "unknown error")
    typer.secho(err, err=True)
    if job_id:
        typer.secho(f"job_id={job_id}", err=True)
    return 1

# ---------------------------------------------------------------------------



def _db_initialized(db_path: Union[str, Path]) -> bool:
    """Return True if DB file exists and ingest_logs table is present.

    The pipeline will not create the DB/schema automatically; use
    scripts/init_ingest_db.py to initialize the database prior to running.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='ingest_logs';"
            )
            return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception:
        return False


def _ensure_metadata_file(metadata_path: Union[str, Path]) -> None:
    """Ensure metadata directory exists and initialize a JSONL file.

    For JSONL metadata files this function ensures the parent directory
    exists and creates an empty file atomically (write to a `.tmp` and
    `os.replace`) if the target file does not exist. It does not attempt
    to initialize a JSON array or modify file contents if the file is
    already present.
    """
    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    if not metadata_path.exists():
        # create an empty file atomically
        tmp = metadata_path.with_suffix(".tmp")
        tmp.write_text("")
        os.replace(str(tmp), str(metadata_path))


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
    """Save DataFrame to raw/<provider>/<ticker>-<ts>.csv and register metadata.

    The function no longer creates the DB or schema. If the DB/schema is not
    present, the CSV and checksum are still written but the metadata is not
    recorded to the SQLite DB; in that case a warning is logged.  Use
    ``scripts/init_ingest_db.py`` to initialize the DB before expecting
    metadata entries to appear.
    """
    if ts is None:
        ts_dt = datetime.now(timezone.utc)
        ts_str = ts_dt.strftime("%Y%m%dT%H%M%SZ")
    elif isinstance(ts, datetime):
        ts_dt = ts.astimezone(timezone.utc)
        ts_str = ts_dt.strftime("%Y%m%dT%H%M%SZ")
    else:
        ts_str = str(ts)

    raw_root = Path(raw_root)
    provider_dir = raw_root / provider
    provider_dir.mkdir(parents=True, exist_ok=True)

    # deterministic column ordering (stable)
    try:
        df_to_save = df.reindex(sorted(df.columns), axis=1)
    except Exception:
        df_to_save = df.copy()

    filename = f"{ticker}-{ts_str}.csv"
    file_path = provider_dir / filename

    job_id = str(uuid.uuid4())
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    created_at = fetched_at
    rows = len(df_to_save)

    try:
        # Serialize dataframe deterministically and write the same bytes
        df_bytes = serialize_df_bytes(
            df_to_save,
            index=True,
            date_format="%Y-%m-%dT%H:%M:%S",
            float_format="%.10g",
            na_rep="",
        )

        _write_bytes_atomic(file_path, df_bytes)

        # Compute checksum from the exact bytes written
        checksum = sha256_bytes(df_bytes)

        # write .checksum file
        checksum_path = Path(f"{str(file_path)}.checksum")
        checksum_path.write_text(checksum)

        if set_permissions:
            _apply_posix_permissions([file_path, Path(f"{str(file_path)}.checksum")])

        metadata = {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": checksum,
            "rows": rows,
            "filepath": str(file_path),
            "status": "success",
            "created_at": created_at,
        }

        try:
            _persist_metadata(metadata, metadata_path)
        except Exception as e_meta:
            _log_metadata_error("Falha ao gravar metadados em JSON", e_meta, metadata)

        return metadata

    except Exception as e:
        logger.exception("Erro ao salvar raw CSV: %s", e)

        metadata = {
            "job_id": job_id,
            "source": provider,
            "fetched_at": fetched_at,
            "raw_checksum": None,
            "rows": rows,
            "filepath": str(file_path),
            "status": "error",
            "error_message": str(e),
            "created_at": created_at,
            "metadata_recorded": False,
        }

        # attempt to persist error metadata to JSON as best-effort
        try:
            _persist_metadata(metadata, metadata_path)
        except Exception as e_meta:
            _log_metadata_error(
                "Falha ao gravar metadados de erro em JSON", e_meta, metadata
            )
        return metadata


# TODO Rename this here and in `save_raw_csv`
def _log_metadata_error(msg: str, e_meta: Exception, metadata: Dict[str, Any]) -> None:
    logger.exception("%s: %s", msg, e_meta)
    metadata["metadata_recorded"] = False
    metadata["metadata_error_message"] = str(e_meta)


# TODO Rename this here and in `save_raw_csv`
def _persist_metadata(
    metadata: Dict[str, Any], metadata_path: Union[str, Path] = DEFAULT_METADATA
) -> None:
    # JSONL append: write a single JSON object per line in append mode.
    _ensure_metadata_file(metadata_path)
    metadata_path = Path(metadata_path)

    line = json.dumps(metadata, ensure_ascii=False)
    # Open, append, flush and fsync for durability
    with open(metadata_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError as exc:
            # Not critical on some platforms; best-effort, but log for diagnosis
            logger.warning("fsync failed for metadata path %s: %s", metadata_path, exc)
    metadata["metadata_recorded"] = True
    metadata["metadata_path"] = str(metadata_path)


def _write_csv_atomic(df: pd.DataFrame, file_path: Union[str, Path]) -> None:
    file_path = Path(file_path)
    filename = file_path.name
    provider_dir = file_path.parent
    fd, tmp = tempfile.mkstemp(prefix=f"{filename}.", dir=str(provider_dir))
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
    file_path = Path(file_path)
    filename = file_path.name
    provider_dir = file_path.parent
    fd, tmp = tempfile.mkstemp(prefix=f"{filename}.", dir=str(provider_dir))
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
    file_path = Path(file_path)
    checksum = sha256_file(file_path)
    checksum_path = Path(f"{str(file_path)}.checksum")
    checksum_path.write_text(checksum)
    return checksum


def _apply_posix_permissions(paths: list[Union[str, Path]]) -> None:
    try:
        if hasattr(os, "chmod"):
            for p in paths:
                os.chmod(str(p), 0o600)
    except Exception:
        logger.exception("Falha ao aplicar permissões aos arquivos")


# ---------------------------------------------------------------------------
# Snapshot caching / incremental ingestion helpers (Story 1.10)
# ---------------------------------------------------------------------------

def _env_bool(name: str) -> bool:
    """Interpret an environment variable as a boolean flag.

    The implementation is deliberately strict: only a small set of values
    are recognised as ``True`` or ``False``.  This prevents typos or
    unexpected strings (``off``, ``flase``) from silently flipping the
    flag.  Unknown values raise :class:`ValueError` so that misconfiguration
    fails fast.

    Recognised truthy values (case-insensitive): ``1``, ``true``, ``yes``.
    Recognised falsy values: ``0``, ``false``, ``no``, ``off`` or the empty
    string.  If the variable is not defined in the environment the result is
    ``False``.
    """
    val = os.environ.get(name)
    if val is None:
        return False

    norm = val.strip().lower()
    true_set = {"1", "true", "yes"}
    false_set = {"0", "false", "no", "off", ""}

    if norm in true_set:
        return True
    if norm in false_set:
        return False

    # unknown input; caller probably mis‑typed the variable name/value
    raise ValueError(f"unexpected boolean env var {name}={val!r}")


def get_snapshot_dir() -> Path:
    """Return the configured snapshot directory.

    Defaults to ``SNAPSHOT_DIR`` environment variable or ``dados/snapshots``
    when the variable is not defined. The path is *not* created by this
    helper.
    """
    if dir_str := os.environ.get("SNAPSHOT_DIR"):
        return Path(dir_str)
    from src.paths import DATA_DIR

    return DATA_DIR / "snapshots"


def get_snapshot_ttl() -> float:
    """Return snapshot TTL in seconds read from ``SNAPSHOT_TTL``.

    The environment variable may contain a floating-point value to allow
    sub-second expiration during tests.  Invalid or missing values are treated
    as ``0`` meaning "no expiry" (the cache will be considered fresh
    indefinitely).
    """
    try:
        return float(os.environ.get("SNAPSHOT_TTL", "0"))
    except ValueError:
        return 0.0


def force_refresh_flag() -> bool:
    """Return ``True`` if ``FORCE_REFRESH`` environment variable is truthy.

    Parsing is strict: only ``1``, ``true`` or ``yes`` (case-insensitive) are
    accepted as true; ``0``, ``false``, ``no`` and ``off`` are false.  Any other
    value will raise :class:`ValueError` so misconfigured environments fail fast.
    """
    return _env_bool("FORCE_REFRESH")




def _rows_to_ingest(df: pd.DataFrame, existing: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Return the subset of ``df`` that should be written to the database.

    The input frame may have a ``date`` column or a ``DatetimeIndex``; the
    returned frame is indexed by ``date`` without resetting.  ``existing``
    represents the canonical data already present for the ticker and may be
    ``None`` or empty.  This helper encapsulates the incremental diff logic
    used both by :func:`ingest_from_snapshot` and the CLI path.
    """

    # normalize caller frame into a datetime index
    df2 = df.copy()
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"])
        df2 = df2.set_index("date")
    elif not isinstance(df2.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have datetime index or 'date' column")

    # coerce timezone differences to UTC, then drop tz info for comparison
    if isinstance(df2.index, pd.DatetimeIndex):
        if df2.index.tz is not None:
            df2.index = df2.index.tz_convert("UTC").tz_localize(None)
        else:
            df2.index = df2.index.tz_localize("UTC").tz_localize(None)

    if existing is None or existing.empty:
        return df2

    existing2 = existing.copy()
    if not isinstance(existing2.index, pd.DatetimeIndex):
        existing2.index = pd.to_datetime(existing2.index)

    # apply same timezone normalization as df2
    if isinstance(existing2.index, pd.DatetimeIndex):
        if existing2.index.tz is not None:
            existing2.index = existing2.index.tz_convert("UTC").tz_localize(None)
        else:
            existing2.index = existing2.index.tz_localize("UTC").tz_localize(None)

    new_idx = df2.index.difference(existing2.index)
    changed_idx = df2.index.intersection(existing2.index)

    ignore_cols = {"raw_checksum", "fetched_at"}
    common = (
        df2.columns.intersection(existing2.columns).difference(list(ignore_cols))
    )
    # prepare placeholders so that lint tools know the variables exist
    df_sub = pd.DataFrame()
    mask_changed = pd.Series(False, index=changed_idx)

    if not common.empty:
        df_sub = df2.loc[changed_idx, common]
        ex_sub = existing2.loc[changed_idx, common]
        df_sub, ex_sub = df_sub.align(ex_sub, join="inner", axis=0)
        mask_changed = (df_sub != ex_sub).any(axis=1)

    changed = pd.DataFrame() if common.empty else df2.loc[df_sub.index[mask_changed]]
    return pd.concat([df2.loc[new_idx], changed])


def ingest_from_snapshot(  # noqa: C901
    df: pd.DataFrame,
    ticker: str,
    *,
    snapshot_dir: Optional[Union[str, Path]] = None,
    ttl: Optional[float] = None,
    force: Optional[bool] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Run cache+incremental ingestion pipeline on a DataFrame.

    The function implements the red/green requirements of story **1-10**:
    * write a versioned snapshot to disk with accompanying SHA256 checksum and
      metadata
    * avoid reprocessing when the checksum is unchanged and the cache has not
      expired (``ttl``)
    * when processing is required, ingest *only* new or changed rows into the
      canonical ``prices`` table using the existing ``db.write_prices`` helper
      (idempotent upsert semantics)

    Parameters
    ----------
    df: pandas.DataFrame
        Source data for the snapshot. May have a ``date`` column or a
        ``DatetimeIndex``; the downstream logic requires a datetime index to
        compute diffs.
    ticker: str
        Identifier used in filenames, metadata, and to query the database.
    snapshot_dir:
        Optional override for the snapshot directory. When ``None`` the value
        from :func:`get_snapshot_dir` is used and the directory is created if
        necessary.
    ttl:
        Cache time‑to‑live in seconds. ``None`` means read ``SNAPSHOT_TTL``
        env var; a non‑positive value bypasses expiration checking.
    force:
        When ``True`` skip cache and always re‑write and ingest. ``None`` reads
        ``FORCE_REFRESH`` environment variable.
    db_path:
        Optional path for the SQLite database. Passed through to the various
        ``db`` helpers so that tests may use a temporary database location.

    Returns
    -------
    dict
        A summary containing at least ``cached`` (bool) and ``rows_processed``
        (int). When a new snapshot is written additional keys ``snapshot_path``
        and ``checksum`` are provided.
    """

    # resolve parameters
    # normalize parameters ------------------------------------------------
    # ``snapshot_dir`` is converted to Path later; ``db_path`` may be a
    # pathlib.Path in tests or user code and the internal :mod:`src.db`
    # helpers expect a string (or None), so cast it here to keep type checkers
    # happy and avoid repeated conversions.
    if db_path is not None:
        db_path = str(db_path)

    if snapshot_dir is None:
        snapshot_dir = get_snapshot_dir()
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    if ttl is None:
        ttl = get_snapshot_ttl()
    if force is None:
        force = force_refresh_flag()

    # compute checksum of dataframe bytes using same serialization options
    # employed by :func:`src.etl.snapshot.write_snapshot`.  This ensures the
    # value stored in metadata (sha returned by write_snapshot) matches the
    # one used during cache lookup.
    data_bytes = serialize_df_bytes(
        df,
        index=False,
        date_format="%Y-%m-%d",
        float_format="%.10g",
        na_rep="",
    )
    checksum = sha256_bytes(data_bytes)

    # attempt to load last metadata entry for ticker from snapshots table
    import src.db as _db

    # incremental diff helper moved to module scope; continue body below

    last_meta = None
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _db._connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT payload FROM snapshots WHERE ticker = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )
        if row := cur.fetchone():
            try:
                last_meta = json.loads(row[0])
            except json.JSONDecodeError as exc:
                # corrupted payload should not abort the whole run but it is
                # worth surfacing for later investigation.
                logger.warning(
                    "invalid snapshot metadata JSON for %s: %s",
                    ticker,
                    exc,
                )
                last_meta = None
    except (OSError, sqlite3.DatabaseError) as exc:
        # treat database or I/O failures as cache misses; keep ingestion
        # resilient but surface potential ongoing operational issues.
        # logged at warning level so that persistent failures in the
        # ``snapshots`` cache are visible in production monitoring.  Also
        # increment a telemetry counter when available.
        logger.warning(
            "snapshot metadata cache fallback in use; failed to read snapshot "
            "metadata for %s: %s",
            ticker,
            exc,
        )
        try:
            from src import metrics

            metrics.increment_counter("snapshot_metadata_cache_fallback")
        except Exception:  # pragma: no cover - metrics optional
            logger.debug("metrics increment failed", exc_info=True)
        last_meta = None
    finally:
        if "conn" in locals() and conn:
            conn.close()

    cache_hit = False
    if last_meta and not force:
        last_sha = last_meta.get("sha256")
        if last_sha == checksum:
            if ttl <= 0:
                cache_hit = True
            else:
                last_ts_str = last_meta.get("generated_at")
                if not last_ts_str:
                    logger.debug(
                        "snapshot metadata for %s missing 'generated_at';"
                        " treating as cache miss",
                        ticker,
                    )
                else:
                    try:
                        last_ts = datetime.fromisoformat(
                            last_ts_str.replace("Z", "+00:00")
                        )
                        age = (datetime.now(timezone.utc) - last_ts).total_seconds()
                        if age < ttl:
                            cache_hit = True
                    except Exception:
                        logger.warning(
                            "invalid 'generated_at' timestamp in snapshot metadata"
                            " for %s: %r; treating as cache miss",
                            ticker,
                            last_ts_str,
                        )
    if cache_hit:
        logger.info("snapshot cache hit for %s (ttl=%s)", ticker, ttl)
        return {"cached": True, "rows_processed": 0}

    # write fresh snapshot and record metadata
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    safe_ticker = ticker.replace(".", "_")
    filename = f"{safe_ticker}-{ts}.csv"
    out_path = snapshot_dir / filename

    from src.etl.snapshot import write_snapshot

    sha = write_snapshot(df, out_path)
    metadata = {
        "snapshot_id": filename,
        "ticker": ticker,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "rows_count": len(df),
        "sha256": sha,
    }
    try:
        _db.record_snapshot_metadata(metadata, db_path=db_path)
    except Exception as e:
        logger.warning("failed to record snapshot metadata: %s", e)

    # incremental ingestion: compute diff against existing canonical data
    try:
        existing = _db.read_prices(ticker, db_path=db_path)
    except Exception:
        existing = None

    # delegate diff logic to shared helper so ingest_cli can reuse it
    rows_to_ingest = _rows_to_ingest(df, existing)
    rows_processed = len(rows_to_ingest)
    if rows_processed > 0:
        _db.write_prices(rows_to_ingest.reset_index(), ticker, db_path=db_path)

    logger.info(
        "ingest_from_snapshot complete for %s: rows_processed=%d, cached=%s",
        ticker,
        rows_processed,
        False,
    )
    result = {"cached": False, "rows_processed": rows_processed}
    result["snapshot_path"] = str(out_path)
    result["checksum"] = sha
    return result
