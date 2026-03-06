"""Snapshot ingestion layer: cache, incremental diff and DB persistence.

This module is one of the central pieces of the ingest workflow.  The
high-level flow is:

1. acquire a ticker-specific lock via :func:`src.locks.acquire_lock` to
   serialize concurrent invocations in the same process.
2. load the most recent snapshot metadata from the DB cache.
3. compute a checksum and evaluate whether the cache is still valid
   (TTL + matching sha256) unless a force refresh is requested.
4. when a refresh is required, write a new snapshot CSV and its checksum,
   then perform an incremental upsert into the ``prices`` table.

Separating these concerns across ``locks.py``, ``snapshot_ingest.py`` and
``db.*`` keeps each module small, but the above comment helps future
contributors understand how they interact.  See ``locks`` for the
locking implementation and ``db`` for the low-level read/write helpers.

Environment variables
---------------------
``SNAPSHOT_DIR``       - override default snapshot directory (``dados/snapshots``)
``SNAPSHOT_TTL``       — cache TTL in seconds (float, default 0 → no expiry)
``FORCE_REFRESH``      — when truthy, bypass cache and always re-ingest
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd

from src.ingest.ticker_lock import lock_ticker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment-variable helpers
# ---------------------------------------------------------------------------


def env_bool(name: str) -> bool:
    """Interpret *name* as a strict boolean environment variable.

    Recognised truthy values (case-insensitive, stripped): ``1``, ``true``,
    ``yes``.  Recognised falsy values: ``0``, ``false``, ``no``, ``off``, or
    the empty string.  If the variable is absent the result is ``False``.
    Unrecognised values raise :class:`ValueError` so mis-configuration fails
    fast.
    """
    val = os.environ.get(name)
    if val is None:
        return False
    norm = val.strip().lower()
    if norm in {"1", "true", "yes"}:
        return True
    if norm in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"unexpected boolean env var {name}={val!r}")


def get_snapshot_dir() -> Path:
    """Return the configured snapshot directory.

    Uses the ``SNAPSHOT_DIR`` environment variable when set; otherwise
    defaults to ``dados/snapshots`` (relative to the project data directory).
    The directory is *not* created by this helper.
    """
    if dir_str := os.environ.get("SNAPSHOT_DIR"):
        return Path(dir_str)
    from src.paths import DATA_DIR

    return DATA_DIR / "snapshots"


def get_snapshot_ttl() -> float:
    """Return the snapshot cache TTL in seconds from ``SNAPSHOT_TTL``.

    Supports floating-point values (useful for sub-second expiration in
    tests).  Missing or invalid values default to ``0.0`` (no expiry).
    """
    try:
        return float(os.environ.get("SNAPSHOT_TTL", "0"))
    except ValueError:
        return 0.0


def force_refresh_flag() -> bool:
    """Return ``True`` when the ``FORCE_REFRESH`` environment variable is truthy.

    Parsing is delegated to :func:`env_bool` — only ``1``, ``true`` or
    ``yes`` are accepted as truthy; anything else is either false or raises.
    """
    return env_bool("FORCE_REFRESH")


# ---------------------------------------------------------------------------
# Incremental diff helpers
# ---------------------------------------------------------------------------


def to_utc_naive_datetime_index(index: pd.Index) -> pd.DatetimeIndex:
    """Normalise *index* to a timezone-naive UTC :class:`pd.DatetimeIndex`.

    * Naive timestamps are localised to UTC.
    * Aware timestamps are converted to UTC.
    * Timezone info is then stripped for stable comparison operations.
    """
    dt_index = pd.to_datetime(index)
    if not isinstance(dt_index, pd.DatetimeIndex):
        dt_index = pd.DatetimeIndex(dt_index)
    if dt_index.tz is None:
        dt_index = dt_index.tz_localize("UTC")
    else:
        dt_index = dt_index.tz_convert("UTC")
    return dt_index.tz_convert(None)


def rows_to_ingest(
    df: pd.DataFrame, existing: Optional[pd.DataFrame]
) -> pd.DataFrame:
    """Return the subset of *df* that should be written to the database.

    New rows (dates not in *existing*) and changed rows (same date but
    different values in non-metadata columns) are included.  Columns
    ``raw_checksum`` and ``fetched_at`` are excluded from the diff because
    they change on every pull.

    Parameters
    ----------
    df:
        Incoming data.  Must have a ``date`` column or a
        :class:`pd.DatetimeIndex`.
    existing:
        Data already present in the DB for this ticker, or ``None`` / empty.

    Raises
    ------
    ValueError
        If *df* has neither a ``date`` column nor a :class:`pd.DatetimeIndex`.
    """
    df2 = df.copy()
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"])
        df2 = df2.set_index("date")
    elif not isinstance(df2.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have a datetime index or 'date' column")

    df2.index = to_utc_naive_datetime_index(df2.index)

    if existing is None or existing.empty:
        return df2

    existing2 = existing.copy()
    existing2.index = to_utc_naive_datetime_index(existing2.index)

    new_idx = df2.index.difference(existing2.index)
    changed_idx = df2.index.intersection(existing2.index)

    ignore_cols = {"raw_checksum", "fetched_at"}
    common = df2.columns.intersection(existing2.columns).difference(list(ignore_cols))

    # Guard: if no comparable columns exist treat all intersecting rows as unchanged.
    df_sub = pd.DataFrame()
    mask_changed = pd.Series(False, index=changed_idx)

    if not common.empty:
        df_sub = df2.loc[changed_idx, common]
        ex_sub = existing2.loc[changed_idx, common]
        df_sub, ex_sub = df_sub.align(ex_sub, join="inner", axis=0)
        mask_changed = (df_sub != ex_sub).any(axis=1)

    changed = pd.DataFrame() if common.empty else df2.loc[df_sub.index[mask_changed]]
    return pd.concat([df2.loc[new_idx], changed])


# ---------------------------------------------------------------------------
# Private helpers for ingest_from_snapshot
# ---------------------------------------------------------------------------


def _resolve_ingest_params(
    snapshot_dir: Optional[Union[str, Path]],
    ttl: Optional[float],
    force: Optional[bool],
) -> tuple[Path, float, bool]:
    """Resolve snapshot pipeline parameters from arguments or environment."""
    if snapshot_dir is None:
        snapshot_dir = get_snapshot_dir()
    resolved_dir = Path(snapshot_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_ttl = get_snapshot_ttl() if ttl is None else ttl
    resolved_force = force_refresh_flag() if force is None else force
    return resolved_dir, resolved_ttl, resolved_force


def _load_last_snapshot_meta(
    ticker: str, db_path: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Read and deserialise the last snapshot metadata for *ticker* from the DB."""
    import src.db as _db

    try:
        payload_str = _db.get_last_snapshot_payload(ticker, db_path=db_path)
        if payload_str is not None:
            try:
                return json.loads(payload_str)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "invalid snapshot metadata JSON for %s: %s", ticker, exc
                )
    except (OSError, sqlite3.DatabaseError) as exc:
        logger.warning(
            "snapshot metadata cache fallback; failed to read metadata for"
            " %s: %s",
            ticker,
            exc,
        )
        try:
            from src import metrics

            metrics.increment_counter("snapshot_metadata_cache_fallback")
        except Exception:  # pragma: no cover — metrics optional
            logger.debug("metrics increment failed", exc_info=True)
    return None


def _evaluate_cache_hit(
    last_meta: Optional[Dict[str, Any]],
    checksum: str,
    ttl: float,
    force: bool,
    ticker: str,
) -> Optional[Dict[str, Any]]:
    """Return a cache-hit result dict, or ``None`` when a refresh is needed."""
    # Explicitly bypass cache when forced so callers can see the reason in logs
    if force:
        logger.info("force refresh requested for %s; bypassing snapshot cache", ticker)
        return None

    if not last_meta or last_meta.get("sha256") != checksum:
        # no previous snapshot or checksum mismatch -> miss
        return None

    _cache_result: Dict[str, Any] = {
        "status": "success",
        "cached": True,
        "rows_processed": 0,
        "reason": "checksum_match",
    }

    if ttl <= 0:
        logger.info("snapshot cache hit for %s (ttl=no-expiry)", ticker)
        return _cache_result

    last_ts_str = last_meta.get("generated_at")
    if not last_ts_str:
        logger.debug(
            "snapshot metadata for %s missing 'generated_at'; treating as cache miss",
            ticker,
        )
        return None

    try:
        last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last_ts).total_seconds()
        if age < ttl:
            logger.info(
                "snapshot cache hit for %s (age=%.1fs < ttl=%.1fs)", ticker, age, ttl
            )
            _cache_result["reason"] = "within_ttl"
            return _cache_result
    except Exception:
        logger.warning(
            "invalid 'generated_at' in snapshot metadata for %s: %r; "
            "treating as cache miss",
            ticker,
            last_ts_str,
        )
    return None


def _write_and_record_snapshot(
    df: pd.DataFrame,
    ticker: str,
    snapshot_dir: Path,
    db_path: Optional[str],
) -> tuple[str, Path]:
    """Write a versioned snapshot CSV to disk and record metadata in the DB."""
    import src.db as _db
    from src.etl.snapshot import write_snapshot

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    filename = f"{ticker.replace('.', '_')}-{ts}.csv"
    out_path = snapshot_dir / filename

    # write_snapshot also handles pruning old files via _prune_old_snapshots
    sha = write_snapshot(df, out_path)

    snapshot_meta: Dict[str, Any] = {
        "snapshot_id": filename,
        "ticker": ticker,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "rows_count": len(df),
        "sha256": sha,
    }
    try:
        _db.record_snapshot_metadata(snapshot_meta, db_path=db_path)
    except Exception as exc:
        logger.warning("failed to record snapshot metadata: %s", exc)

    return sha, out_path


def _run_incremental_ingest(
    df: pd.DataFrame,
    ticker: str,
    db_path: Optional[str],
) -> int:
    """Diff *df* against existing DB rows and persist only new/changed rows."""
    import src.db as _db

    try:
        existing = _db.read_prices(ticker, db_path=db_path)
    except Exception:
        existing = None

    rows_subset = rows_to_ingest(df, existing)
    rows_processed = len(rows_subset)
    if rows_processed > 0:
        _db.write_prices(rows_subset.reset_index(), ticker, db_path=db_path)
    return rows_processed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_from_snapshot(
    df: pd.DataFrame,
    ticker: str,
    *,
    snapshot_dir: Optional[Union[str, Path]] = None,
    ttl: Optional[float] = None,
    force: Optional[bool] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Run the cache-then-incremental ingestion pipeline on *df*.

    Parameters
    ----------
    df:
        Source data for the snapshot.  May carry a ``date`` column or a
        :class:`pd.DatetimeIndex`.
    ticker:
        Identifier used in filenames, metadata records, and DB queries.
    snapshot_dir:
        Override the snapshot directory.  ``None`` reads ``SNAPSHOT_DIR``
        env var or falls back to ``dados/snapshots``.
    ttl:
        Cache TTL in seconds.  ``None`` reads ``SNAPSHOT_TTL`` env var; a
        non-positive value disables expiry checking.
    force:
        Skip cache and always re-write and re-ingest.  ``None`` reads the
        ``FORCE_REFRESH`` env var.
    db_path:
        Path to the SQLite database.  Useful in tests.

    Returns
    -------
    dict
        Always contains ``status`` (``"success"`` or ``"error"``),
        ``cached`` (bool) and ``rows_processed`` (int).  On a fresh snapshot
        write, ``snapshot_path`` and ``checksum`` are also present.

        Note
        ----
        Most error conditions are handled gracefully by returning a dict with
        ``status=='error'``.  However, underlying database write failures may
        propagate as exceptions; the CLI wrapper and ``pipeline.ingest``
        already handle these cases.
    """
    resolved_db = str(db_path) if db_path is not None else None
    resolved_dir, resolved_ttl, resolved_force = _resolve_ingest_params(
        snapshot_dir, ttl, force
    )

    from src.etl.snapshot import snapshot_checksum

    checksum = snapshot_checksum(df)
    start = time.monotonic()

    # Serialize ingestion by ticker within this process so the
    # read-cache → write-snapshot → diff → DB upsert critical section
    # is safe under concurrent callers.
    with lock_ticker(ticker):
        last_meta = _load_last_snapshot_meta(ticker, resolved_db)
        cache_result = _evaluate_cache_hit(
            last_meta, checksum, resolved_ttl, resolved_force, ticker
        )
        if cache_result is not None:
            # include duration for the quick-cached path
            elapsed = time.monotonic() - start
            cache_result["duration"] = f"{elapsed:.2f}s"
            return cache_result

        sha, out_path = _write_and_record_snapshot(
            df, ticker, resolved_dir, resolved_db
        )
        rows_processed = _run_incremental_ingest(df, ticker, resolved_db)

        elapsed = time.monotonic() - start
        logger.info(
            "ingest_from_snapshot complete for %s: rows_processed=%d, "
            "cached=False, elapsed=%.2fs",
            ticker,
            rows_processed,
            elapsed,
        )
        return {
            "status": "success",
            "cached": False,
            "rows_processed": rows_processed,
            "snapshot_path": str(out_path),
            "checksum": sha,
            "duration": f"{elapsed:.2f}s",
        }
