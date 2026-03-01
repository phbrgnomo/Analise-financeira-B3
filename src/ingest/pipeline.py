"""Ingest pipeline orchestration.

This module wires together the adapter factory, the canonical mapper,
raw-CSV persistence and snapshot ingestion into a single coherent
:func:`ingest` function, and exposes an :func:`ingest_command` CLI wrapper
for Typer.

Persistence details live in :mod:`src.ingest.raw_storage`.
Snapshot caching and incremental diff logic live in
:mod:`src.ingest.snapshot_ingest`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import typer  # used by ingest_command error handling

# Re-export constants and helpers so existing callers keep working without
# updating their import paths.
from src.ingest.raw_storage import (  # noqa: F401
    DEFAULT_DB,
    DEFAULT_METADATA,
    record_ingest_metadata,
    save_raw_csv,
)
from src.ingest.snapshot_ingest import (  # noqa: F401
    env_bool,
    force_refresh_flag,
    get_snapshot_dir,
    get_snapshot_ttl,
    ingest_from_snapshot,
    rows_to_ingest,
    to_utc_naive_datetime_index,
)
from src.tickers import normalize_b3_ticker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private alias for backwards compatibility within this module
# ---------------------------------------------------------------------------

# Kept so any in-process caller that called the module-private name directly
# continues to work during the transition period.
_record_ingest_metadata = record_ingest_metadata


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
    try:
        canonical_ticker = normalize_b3_ticker(ticker)
    except ValueError:
        canonical_ticker = ticker.strip().upper()

    job_id = str(uuid.uuid4())
    logger.info(
        "pipeline.ingest start",
        extra={
            "job_id": job_id,
            "ticker": canonical_ticker,
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
            "ticker": canonical_ticker,
            "source": source,
            "status": "error",
            "error_message": msg,
        }
        _record_ingest_metadata(metadata)
        return {"job_id": job_id, "status": "error", "error_message": msg}

    # map to canonical
    try:
        from src.etl.mapper import to_canonical

        canonical = to_canonical(
            df,
            provider_name=source,
            ticker=canonical_ticker,
        )
    except Exception as exc:  # mapper failure
        msg = f"mapper failed: {exc}"
        logger.exception(msg)
        metadata = {
            "job_id": job_id,
            "ticker": canonical_ticker,
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
            "ticker": ticker,
            "source": source,
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
            "ticker": canonical_ticker,
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
        persist_result = ingest_from_snapshot(
            canonical,
            canonical_ticker,
            force=force_refresh,
        )
    except Exception as exc:  # pragma: no cover - just in case
        logger.exception("persistence step failed: %s", exc)
        persist_result = {"status": "error", "error_message": str(exc)}

    # Derive overall status from persistence outcome.
    #
    # Backwards compatibility: older `ingest_from_snapshot` responses did not
    # include an explicit `status` field and only returned keys like
    # `cached`/`rows_processed`. In that case, treat the persistence step as
    # successful unless there is an explicit error signal.
    persist_status = persist_result.get("status")
    if persist_status is None:
        # Explicit parentheses to make operator precedence (and > or) unambiguous:
        # treat as error only when there is an error_message OR both cached and
        # rows_processed are absent (meaning we got back an empty/unexpected dict).
        has_error_signal = persist_result.get("error_message") is not None or (
            persist_result.get("cached") is None
            and persist_result.get("rows_processed") is None
        )
        top_status = "error" if has_error_signal else "success"
    elif persist_status == "success":
        top_status = "success"
    elif persist_status == "error":
        top_status = "error"
    else:
        logger.warning(
            "Unexpected persist_result.status '%s'; treating as success",
            persist_status,
        )
        top_status = "success"

    # final metadata entry for the orchestrator run
    metadata = {
        "job_id": job_id,
        "ticker": canonical_ticker,
        "source": source,
        "status": top_status,
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
        "status": top_status,
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
