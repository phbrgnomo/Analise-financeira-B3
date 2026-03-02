"""Snapshot ingestion layer: cache, incremental diff and DB persistence.

Implements the red/green requirements of Story 1-10:

* Write a versioned snapshot to disk with an accompanying SHA256 checksum and
  metadata record.
* Skip re-processing when the snapshot checksum is unchanged and the cache
  has not expired (*ttl*).
* When processing is required, ingest *only* new or changed rows into the
  canonical ``prices`` table via ``src.db.write_prices`` (idempotent upsert).

Environment variables
---------------------
``SNAPSHOT_DIR``       — override default snapshot directory (``dados/snapshots``)
``SNAPSHOT_TTL``       — cache TTL in seconds (float, default 0 → no expiry)
``FORCE_REFRESH``      — when truthy, bypass cache and always re-ingest
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd

from src.ingest.ticker_lock import lock_ticker
from src.utils.checksums import serialize_df_bytes, sha256_bytes

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
# Public API
# ---------------------------------------------------------------------------


def ingest_from_snapshot(  # noqa: C901
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
        ``status=='error'`` (the returned dictionary will contain an
        ``error_message`` field describing what went wrong).  However, if an
        underlying database write fails (for example, due to a locked file or
        corrupted database), the function will propagate the exception rather
        than returning a status dict; callers that do not wrap the call may
        see the exception bubble up.  The CLI wrapper and ``pipeline.ingest``
        already catch such exceptions and convert them to an error status for
        the caller.
    """
    # Resolve parameters ---------------------------------------------------
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

    # Compute incoming checksum --------------------------------------------
    data_bytes = serialize_df_bytes(
        df,
        index=False,
        date_format="%Y-%m-%d",
        float_format="%.10g",
        na_rep="",
    )
    checksum = sha256_bytes(data_bytes)

    # Serialize ingestion by ticker within this process. This protects the
    # read-cache -> write-snapshot -> diff -> DB upsert critical section.
    with lock_ticker(ticker):
        # Read last snapshot metadata from DB (best-effort) ----------------
        import src.db as _db  # deferred to avoid circular imports at module load

        last_meta: Optional[Dict[str, Any]] = None
        try:
            payload_str = _db.get_last_snapshot_payload(
                ticker, db_path=db_path
            )
            if payload_str is not None:
                try:
                    last_meta = json.loads(payload_str)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "invalid snapshot metadata JSON for %s: %s", ticker, exc
                    )
        except (OSError, sqlite3.DatabaseError) as exc:
            logger.warning(
                "snapshot metadata cache fallback; failed to read metadata for %s: %s",
                ticker,
                exc,
            )
            try:
                from src import metrics

                metrics.increment_counter("snapshot_metadata_cache_fallback")
            except Exception:  # pragma: no cover — metrics optional
                logger.debug("metrics increment failed", exc_info=True)

        # Cache hit check ---------------------------------------------------
        if last_meta and not force:
            last_sha = last_meta.get("sha256")
            if last_sha == checksum:
                if ttl <= 0:
                    logger.info("snapshot cache hit for %s (ttl=no-expiry)", ticker)
                    return {
                        "status": "success",
                        "cached": True,
                        "rows_processed": 0,
                    }
                if last_ts_str := last_meta.get("generated_at"):
                    try:
                        last_ts = datetime.fromisoformat(
                            last_ts_str.replace("Z", "+00:00")
                        )
                        age = (datetime.now(timezone.utc) - last_ts).total_seconds()
                        if age < ttl:
                            logger.info(
                                "snapshot cache hit for %s (age=%.1fs < ttl=%.1fs)",
                                ticker,
                                age,
                                ttl,
                            )
                            return {
                                "status": "success",
                                "cached": True,
                                "rows_processed": 0,
                            }
                    except Exception:
                        logger.warning(
                            "invalid 'generated_at' in snapshot metadata for %s: %r;"
                            " treating as cache miss",
                            ticker,
                            last_ts_str,
                        )
                else:
                    logger.debug(
                        "snapshot metadata for %s missing 'generated_at';"
                        " treating as cache miss",
                        ticker,
                    )

        # Write fresh snapshot ---------------------------------------------
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y%m%dT%H%M%SZ")
        filename = f"{ticker.replace('.', '_')}-{ts}.csv"
        out_path = snapshot_dir / filename

        from src.etl.snapshot import write_snapshot

        sha = write_snapshot(df, out_path)

        # cleanup older snapshot files for this ticker to avoid buildup
        # support environment variable for how many recent files to keep
        keep = int(os.environ.get("SNAPSHOTS_KEEP_LATEST", "1"))
        sanitized = ticker.replace(".", "_")
        pattern = f"{sanitized}*"  # names start with sanitized ticker
        all_files = sorted(snapshot_dir.glob(pattern))

        # construct regex that matches names beginning with the sanitized
        # ticker
        # followed by end-of-string or a non-alphanumeric delimiter. this
        # guards against removing files for tickers like ABC when cleaning up
        # ABCDEF.
        regex = re.compile(rf"^{re.escape(sanitized)}(?:$|[^A-Za-z0-9])")

        # filter only csv files that truly belong to this ticker
        csv_files = [
            f
            for f in all_files
            if f.suffix == ".csv" and regex.match(f.name)
        ]
        # keep newest `keep` files (alphabetical order corresponds to time)
        to_remove = csv_files[:-keep] if keep > 0 else csv_files
        for old in to_remove:
            try:
                old.unlink()
            except Exception:
                logger.warning("failed to remove old snapshot %s", old)
            # also remove corresponding checksum
            chk = old.with_suffix(old.suffix + ".checksum")
            with contextlib.suppress(Exception):
                chk.unlink()

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

        # Incremental ingestion --------------------------------------------
        try:
            existing = _db.read_prices(ticker, db_path=db_path)
        except Exception:
            existing = None

        rows_subset = rows_to_ingest(df, existing)
        rows_processed = len(rows_subset)
        if rows_processed > 0:
            _db.write_prices(rows_subset.reset_index(), ticker, db_path=db_path)

        logger.info(
            "ingest_from_snapshot complete for %s: rows_processed=%d, cached=False",
            ticker,
            rows_processed,
        )
        return {
            "status": "success",
            "cached": False,
            "rows_processed": rows_processed,
            "snapshot_path": str(out_path),
            "checksum": sha,
        }
