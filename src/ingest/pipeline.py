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
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import typer

from src.cli_feedback import CliFeedback, format_duration

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

# default locations are exported by raw_storage; mirror pattern here
DEFAULT_SAMPLES_DIR = Path("dados") / "samples"


def _now_iso() -> str:
    """Return current UTC time as an RFC3339 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


logger = logging.getLogger(__name__)


def _safe_filename_token(value: str) -> str:
    """Return a filesystem-safe token preserving common ticker characters."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def _resolve_sample_window(
    days: int,
    start: str | None,
    end: str | None,
) -> tuple[str, str]:
    """Resolve date window for sample pulls using UTC calendar dates."""
    now = datetime.now(timezone.utc).date()

    end_date = now.strftime("%Y-%m-%d") if end is None else end

    if start is not None:
        return start, end_date

    safe_days = max(1, days)
    start_date = (now - timedelta(days=safe_days)).strftime("%Y-%m-%d")
    return start_date, end_date


def pull_sample(
    ticker: str,
    source: str = "yfinance",
    *,
    days: int = 10,
    start: str | None = None,
    end: str | None = None,
    output: str | None = None,
    samples_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Fetch provider data and export raw/canonical CSV sample artifacts.

    This command is intended as a visual smoke-test helper for adapter output,
    canonical mapping, and schema validation, without any database persistence.
    """
    try:
        canonical_ticker = normalize_b3_ticker(ticker)
    except ValueError:
        canonical_ticker = ticker.strip().upper()

    job_id = str(uuid.uuid4())
    started_at = _now_iso()

    try:
        from src.adapters.factory import get_adapter
        from src.etl.mapper import to_canonical

        adapter = get_adapter(source)
        start_date, end_date = _resolve_sample_window(days, start, end)
        raw_df = adapter.fetch(
            canonical_ticker,
            start_date=start_date,
            end_date=end_date,
        )

        if raw_df.empty:
            msg = (
                f"provider returned empty DataFrame for {canonical_ticker} "
                f"in range {start_date}..{end_date}"
            )
            metadata = {
                "job_id": job_id,
                "ticker": canonical_ticker,
                "source": source,
                "status": "error",
                "error_message": msg,
                "started_at": started_at,
                "finished_at": _now_iso(),
            }
            _record_ingest_metadata(metadata)
            return {"job_id": job_id, "status": "error", "error_message": msg}

        canonical_df = to_canonical(
            raw_df,
            provider_name=source,
            ticker=canonical_ticker,
        )

        safe_ticker = _safe_filename_token(canonical_ticker)
        safe_source = _safe_filename_token(source)
        # resolve samples directory (configure via parameter or SAMPLES_DIR env var)
        if samples_dir is not None:
            samples_path = Path(samples_dir)
        else:
            env_val = os.getenv("SAMPLES_DIR")
            samples_path = Path(env_val) if env_val else DEFAULT_SAMPLES_DIR
        samples_path.mkdir(parents=True, exist_ok=True)

        raw_out = samples_path / f"{safe_ticker}_{safe_source}_raw.csv"
        raw_to_write = raw_df
        if "Date" not in raw_to_write.columns and "date" not in raw_to_write.columns:
            raw_to_write = raw_to_write.reset_index()
        raw_to_write.to_csv(raw_out, index=False)

        canonical_out = (
            Path(output)
            if output
            else samples_path / f"{safe_ticker}_{safe_source}_sample.csv"
        )
        canonical_out.parent.mkdir(parents=True, exist_ok=True)
        canonical_df.to_csv(canonical_out, index=False)

        metadata = {
            "job_id": job_id,
            "ticker": canonical_ticker,
            "source": source,
            "status": "success",
            "rows": len(canonical_df),
            "raw_output": str(raw_out),
            "canonical_output": str(canonical_out),
            "started_at": started_at,
            "finished_at": _now_iso(),
        }
        _record_ingest_metadata(metadata)

        return {
            "job_id": job_id,
            "status": "success",
            "rows": len(canonical_df),
            "raw_output": str(raw_out),
            "canonical_output": str(canonical_out),
        }
    except Exception as exc:  # pragma: no cover - defensive orchestration
        msg = f"pull_sample failed: {exc}"
        logger.exception(msg)
        metadata = {
            "job_id": job_id,
            "ticker": canonical_ticker,
            "source": source,
            "status": "error",
            "error_message": msg,
            "started_at": started_at,
            "finished_at": _now_iso(),
        }
        _record_ingest_metadata(metadata)
        return {"job_id": job_id, "status": "error", "error_message": msg}


def pull_sample_command(
    ticker: str,
    source: str = "yfinance",
    *,
    days: int = 10,
    start: str | None = None,
    end: str | None = None,
    output: str | None = None,
) -> int:
    """CLI-friendly wrapper for sample pulling with adapter/mapper pipeline."""
    feedback = CliFeedback("pipeline pull-sample")
    feedback.start(
        f"ticker={ticker} | source={source} | days={days} | "
        f"start={start or '-'} | end={end or '-'}"
    )
    t0 = time.monotonic()

    result = pull_sample(
        ticker,
        source,
        days=days,
        start=start,
        end=end,
        output=output,
    )

    job_id = result.get("job_id")
    if result.get("status") == "success":
        if job_id:
            print(f"job_id={job_id}")
        feedback.info(f"raw: {result.get('raw_output')}")
        feedback.info(f"canonical: {result.get('canonical_output')}")
        feedback.info(f"rows: {result.get('rows')}")
        elapsed = time.monotonic() - t0
        feedback.summary(f"completed in {format_duration(elapsed)}")
        return 0

    err = result.get("error_message", "unknown error")
    feedback.error(err)
    if job_id:
        typer.secho(f"job_id={job_id}", err=True)
    return 1


# ---------------------------------------------------------------------------
# Private alias for backwards compatibility within this module
# ---------------------------------------------------------------------------

# Kept so any in-process caller that called the module-private name directly
# continues to work during the transition period.
_record_ingest_metadata = record_ingest_metadata


# helper for building metadata dictionaries used in ingest()


def _make_metadata(
    job_id: str,
    ticker: str,
    source: str,
    status: str,
    started_at: str,
    finished_at: str | None = None,
    **extras: Any,
) -> Dict[str, Any]:
    """Return a metadata dict populated with common ingest fields.

    Accepts arbitrary ``extras`` which are merged into the result.  This
    reduces duplication and ensures all branches record the same base set of
    keys (``job_id``, ``ticker``, ``source``, ``status``, ``started_at``,
    ``finished_at``) before any specialized values are added.
    """
    # guard against callers passing reserved keys again via **extras;
    # remove them silently so they cannot clobber the canonical values.
    # we also want to surface the fact that extras contained those keys so
    # callers can diagnose unexpected duplicates.
    removed: list[str] = []
    for key in ("job_id", "ticker", "source", "status", "started_at", "finished_at"):
        if key in extras:
            removed.append(key)
            extras.pop(key, None)
    if removed:
        logger.debug(
            "removendo chaves reservadas de extras em _make_metadata: %s",
            ", ".join(removed),
            extra={"job_id": job_id, "ticker": ticker},
        )

    out: Dict[str, Any] = {
        "job_id": job_id,
        "ticker": ticker,
        "source": source,
        "status": status,
        "started_at": started_at,
    }
    out["finished_at"] = finished_at or _now_iso()
    out.update(extras)
    return out


def ingest(  # noqa: C901 - function is intentionally orchestrator-style
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
    started_at = _now_iso()
    t0 = time.monotonic()
    logger.info(
        "pipeline.ingest start",
        extra={
            "job_id": job_id,
            "ticker": canonical_ticker,
            "source": source,
            "dry_run": dry_run,
            "force_refresh": force_refresh,
            "started_at": started_at,
        },
    )

    # ------------------------------------------------------------------
    # Story 1.9: bloqueio por ticker para evitar ingestões concorrentes
    # ------------------------------------------------------------------
    # parsing of the environment variables has been pulled into a shared
    # helper so that both this module and other callers (e.g. tests) can
    # rely on the same validation logic and it is easier to extend later.
    from src.ingest.config import get_ingest_lock_settings

    lock_timeout, lock_mode, wait_for_lock = get_ingest_lock_settings()

    # import inside this section so the module can be imported without a
    # hard dependency on the locking machinery (tests and other helpers may
    # not require it).  Using the native context manager form keeps the
    # acquisition/release lifecycle simple and avoids manual __enter__/__exit__
    # which can easily be forgotten during refactors.
    from src import locks

    # record when we begin attempting to acquire the lock so that we can
    # compute the real elapsed wait if a timeout occurs.  ``time.monotonic()``
    # is used because it is immune to system clock adjustments.
    lock_acquire_start = time.monotonic()

    try:
        with locks.acquire_lock(
            ticker, timeout_seconds=lock_timeout, wait=wait_for_lock
        ) as lock_meta:
            # merge any lock metadata into our logging context so downstream
            # steps can include it if they wish (useful for debugging at scale).
            # By creating a new LoggerAdapter we avoid rebinding the global
            # ``logger`` name which would conflict with earlier references.
            log = logging.LoggerAdapter(logger, extra={**lock_meta})

            # fetch
            try:
                from src.adapters.factory import get_adapter

                adapter = get_adapter(source)
                df = adapter.fetch(ticker)
            except Exception as exc:  # fetch failure
                msg = f"adapter.fetch failed: {exc}"
                logger.exception(msg)
                metadata = _make_metadata(
                    job_id,
                    ticker,
                    source,
                    "error",
                    started_at,
                    error_message=msg,
                )
                _record_ingest_metadata(metadata)
                return {"job_id": job_id, "status": "error", "error_message": msg}

            # map to canonical
            try:
                from src.etl.mapper import to_canonical

                canonical = to_canonical(df, provider_name=source, ticker=ticker)
            except Exception as exc:  # mapper failure
                msg = f"mapper failed: {exc}"
                logger.exception(msg)
                metadata = _make_metadata(
                    job_id,
                    ticker,
                    source,
                    "error",
                    started_at,
                    error_message=msg,
                )
                _record_ingest_metadata(metadata)
                return {"job_id": job_id, "status": "error", "error_message": msg}

            # if the caller only wanted a dry run, return now
            if dry_run:
                log.info(
                    "dry run completed",
                    extra={"job_id": job_id, "rows": len(canonical)},
                )
                result = {
                    "job_id": job_id,
                    "ticker": ticker,
                    "source": source,
                    "status": "success",
                    "dry_run": True,
                    "rows": len(canonical),
                    **lock_meta,
                }
                # record metadata even for dry runs to make lock activity visible
                metadata = _make_metadata(
                    job_id,
                    ticker,
                    source,
                    "success",
                    started_at,
                    duration=f"{(time.monotonic() - t0):.2f}s",
                    dry_run=True,
                    rows=len(canonical),
                    **lock_meta,
                )
                _record_ingest_metadata(metadata)
                return result

            # persist raw CSV (Story 1.4)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            try:
                save_meta = save_raw_csv(
                    df, source, ticker, ts, orchestrator_job_id=job_id
                )
            except Exception as exc:
                msg = f"failed to save raw CSV: {exc}"
                logger.exception(msg)
                metadata = _make_metadata(
                    job_id,
                    ticker,
                    source,
                    "error",
                    started_at,
                    error_message=msg,
                )
                _record_ingest_metadata(metadata)
                return {"job_id": job_id, "status": "error", "error_message": msg}

            # attempt DB persistence with snapshot helper; the helper already logs its
            # own metadata.  ``ingest_from_snapshot`` is defined later in this module
            # so we can call it directly instead of importing ourselves at runtime.
            persist_result: Dict[str, Any] = {}
            try:
                persist_result = ingest_from_snapshot(
                    canonical, ticker, force=force_refresh
                )
            except Exception as exc:  # pragma: no cover - just in case
                logger.exception("persistence step failed: %s", exc)
                persist_result = {"status": "error", "error_message": str(exc)}

            # derive overall status from persistence outcome; if the helper reports
            # "error" we propagate that.  Future extensions could use
            # "partial_success" or similar.
            # treat absence of an explicit status as success (legacy behavior)
            pers_status = persist_result.get("status")
            if pers_status is None:
                top_status = "success"
            else:
                top_status = "success" if pers_status == "success" else "error"

            # final metadata entry for the orchestrator run
            duration_str = f"{(time.monotonic() - t0):.2f}s"
            metadata = {
                "job_id": job_id,
                "ticker": ticker,
                "source": source,
                "status": top_status,
                "rows": len(canonical),
                "persist": persist_result,
                "started_at": started_at,
                "finished_at": _now_iso(),
                "duration": duration_str,
                **lock_meta,
            }
            _record_ingest_metadata(metadata)
            logger.info(
                "pipeline.ingest completed",
                extra={
                    "job_id": job_id,
                    "rows": len(canonical),
                    "duration": duration_str,
                    "force_refresh": force_refresh,
                },
            )

            return {
                "job_id": job_id,
                "status": top_status,
                "save_meta": save_meta,
                "persist": persist_result,
                "duration": duration_str,
                **lock_meta,
            }
    except locks.LockTimeout as exc:
        # record a metadata entry indicating the lock failure and bail out
        action = "timeout" if wait_for_lock else "exit"
        if not wait_for_lock:
            # non-blocking/exit mode should never incur a wait
            waited = 0.0
        else:
            # compute actual waited time if we recorded a start timestamp;
            # fall back to configured timeout if somehow ``lock_acquire_start``
            # isn't available (should never happen).
            try:
                waited = time.monotonic() - lock_acquire_start
            except NameError:
                waited = lock_timeout
        msg = f"could not obtain lock for ticker {ticker}: {exc}"
        logger.warning(msg)
        metadata = _make_metadata(
            job_id,
            ticker,
            source,
            "error",
            started_at,
            lock_action=action,
            lock_waited_seconds=waited,
            error_message=msg,
        )
        _record_ingest_metadata(metadata)
        return {"job_id": job_id, "status": "error", "error_message": msg}


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
    feedback = CliFeedback("pipeline ingest")
    feedback.start(
        f"ticker={ticker} | source={source} | dry_run={dry_run} | "
        f"force_refresh={force_refresh}"
    )

    try:
        result = ingest(ticker, source, dry_run=dry_run, force_refresh=force_refresh)
    except Exception as exc:  # pragma: no cover - defensive
        feedback.error(f"fatal error: {exc}")
        return 1

    job_id = result.get("job_id")
    # successful outcome
    if result.get("status") == "success":
        if job_id:
            print(f"job_id={job_id}")
        if dry_run:
            feedback.info("dry run completed; no data written")
        # surface duration and reason for the run when available
        duration = result.get("duration")
        # obter motivo de persistência de maneira segura: encadeamento de
        # chamadas get já retorna None se qualquer chave estiver ausente.
        reason = result.get("persist", {}).get("reason")
        if duration or reason:
            parts = []
            if duration:
                parts.append(f"Completed in {duration}")
            if reason:
                parts.append(f"reason: {reason}")
            feedback.success(" — ".join(parts))
        else:
            feedback.success("completed")
        return 0

    # failure path: log to stderr so stdout remains parsable
    err = result.get("error_message", "unknown error")
    feedback.error(err)
    if job_id:
        typer.secho(f"job_id={job_id}", err=True)
    return 1
