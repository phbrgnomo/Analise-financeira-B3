"""Camada de ingestão de snapshot: cache, diff incremental e persistência no BD.

Este módulo é uma das peças centrais do fluxo de ingestão. O fluxo de alto
nível é:

1. adquirir um bloqueio específico por ticker via :func:`src.locks.acquire_lock`
   para serializar invocações concorrentes no mesmo processo.
2. ler o cache de snapshots de um arquivo JSON para evitar reprocessar dados já
   ingeridos.
3. calcular um checksum e avaliar se o cache ainda é válido (TTL + sha256
   coincidente) a menos que um refresh for forçado.
4. quando um refresh é necessário, gravar um novo CSV de snapshot e seu
   checksum, então executar um upsert incremental na tabela ``prices``.

Separar essas preocupações entre ``locks.py``, ``snapshot_ingest.py`` e
``db.*`` mantém cada módulo pequeno, mas o comentário acima ajuda futuros
colaboradores a entender como eles interagem. Veja ``locks`` para a
implementação de bloqueio e ``db`` para os helpers de leitura/gravação
de baixo nível.

Variáveis de ambiente
---------------------
``SNAPSHOT_DIR``       - sobrescreve o diretório padrão de snapshots
                         (``dados/snapshots``)
``SNAPSHOT_TTL``       — TTL de cache em segundos (float, padrão 0 → sem
                         expiração)
``FORCE_REFRESH``      — quando truthy, ignora o cache e reinveste sempre
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd

from src.ingest.cache import load_cache, save_cache
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


def rows_to_ingest(df: pd.DataFrame, existing: Optional[pd.DataFrame]) -> pd.DataFrame:
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


def _get_snapshot_cache_file(snapshot_dir: Path) -> Path:
    """Return the file path used to persist the snapshot cache.

    The cache is a JSON file mapping snapshot file paths to checksum/processed
    timestamps. It is used to avoid reprocessing unchanged snapshots.

    The path can be overridden via the ``SNAPSHOT_CACHE_FILE`` environment
    variable (useful for tests and custom setups)."""

    if cache_path := os.environ.get("SNAPSHOT_CACHE_FILE"):
        return Path(cache_path)
    return snapshot_dir / "snapshot_cache.json"


def _load_snapshot_cache(cache_file_path: Path) -> Dict[str, Any]:
    """Load the snapshot cache, handling read errors gracefully.

    When the cache file cannot be read, we log a warning and increment a
    metrics counter (if available). This mirrors the behavior of the previous
    metadata-based cache fallback.

    This function also builds an auxiliary index mapping (ticker, sha256)
    to snapshot path so callers can perform O(1) cache lookups for checksum
    hits across renamed snapshot paths.
    """

    try:
        cache_data = load_cache(cache_file_path)
    except Exception as exc:  # pragma: no cover - best effort fallback
        logger.warning(
            "snapshot cache fallback; failed to read cache %s: %s",
            cache_file_path,
            exc,
        )
        try:
            from src.utils import metrics_prometheus as metrics

            metrics.increment_counter("snapshot_cache_fallback")
        except Exception:  # pragma: no cover — metrics optional
            logger.debug("metrics increment failed", exc_info=True)
        cache_data = {}

    # Build the secondary lookup index (ticker,sha256) -> snapshot path.
    cache_index: Dict[str, str] = {}
    for path, entry in cache_data.items():
        if path == "__meta__":
            continue
        if isinstance(entry, dict):
            ticker = entry.get("ticker")
            sha = entry.get("sha256")
            if isinstance(ticker, str) and isinstance(sha, str):
                cache_index[f"{ticker}|{sha}"] = path

    cache_data.setdefault("__meta__", {})["snapshot_index"] = cache_index
    return cache_data


def _safe_snapshot_path(ticker: str, snapshot_dir: Path, ts: str) -> Path:
    """Compute the resolved snapshot file path for a given ticker.

    This helper centralises how snapshot file paths are constructed so both
    cache lookups and writes use the same logic.

    It performs the following steps:

    - sanitises *ticker* to allow only alphanumeric characters, ``-`` and
      ``_`` (everything else becomes ``_``)
    - creates a filename ``{safe_ticker}-{ts}.csv``
    - resolves *snapshot_dir* and verifies the output is inside it

    Raises:
        ValueError: if the resolved path would escape *snapshot_dir*.
    """

    import re

    safe_ticker = re.sub(r"[^A-Za-z0-9_-]", "_", ticker) or "ticker"
    filename = f"{safe_ticker}-{ts}.csv"
    snapshot_dir_res = snapshot_dir.resolve()
    out_path = (snapshot_dir_res / filename).resolve()
    if not out_path.is_relative_to(snapshot_dir_res):
        raise ValueError("sanitized filename escapes snapshot_dir")
    return out_path


def _snapshot_path_for_ticker(ticker: str, snapshot_dir: Path, ts: str) -> Path:
    """Compute the deterministic snapshot file path for a given ticker.

    The snapshot file name is based on the provided date string (YYYYMMDD)
    and a sanitized ticker. This is used to determine the cache lookup key
    before the file exists.
    """

    return _safe_snapshot_path(ticker, snapshot_dir, ts)


def _lookup_cache_by_ticker_and_checksum(
    cache_file: Dict[str, Any],
    ticker: str,
    checksum: str,
) -> Optional[tuple[str, Dict[str, Any]]]:
    """Return snapshot path and entry by (ticker, checksum).

    Parameters:
        cache_file: loaded snapshot cache structure; file paths map to entry dicts.
        ticker: normalized ticker to match (e.g., "PETR4").
        checksum: snapshot SHA256 checksum string to match.

    Returns:
        A tuple (path, entry) when a matching snapshot is found, otherwise None.

    Behavior:
        Tries meta-based index lookup via cache_file["__meta__"]["snapshot_index"]
        for O(1) resolution; if not available falls back to scanning all entries.
    """
    # Uses index in cache_file["__meta__"]["snapshot_index"] when available,
    # falling back to full scan as a compatibility path.
    cache_index = None
    meta = cache_file.get("__meta__")
    if isinstance(meta, dict):
        cache_index = meta.get("snapshot_index")

    if isinstance(cache_index, dict):
        hit_path = cache_index.get(f"{ticker}|{checksum}")
        if hit_path:
            entry = cache_file.get(hit_path)
            if isinstance(entry, dict) and entry.get("sha256") == checksum:
                return hit_path, entry
    for path, data in cache_file.items():
        if (
            isinstance(data, dict)
            and data.get("sha256") == checksum
            and data.get("ticker") == ticker
        ):
            return path, data
    return None


def _check_cache_hit(
    cache_file: Dict[str, Any],
    snapshot_path: Path,
    checksum: str,
    ttl: float,
    force: bool,
    ticker: str,
) -> Optional[Dict[str, Any]]:
    """Return a cache-hit dict or ``None`` when a refresh is needed.

    The cache is stored as a JSON mapping of snapshot path -> metadata.

    The cache key is the snapshot file path, but we also allow hits based on
    checksum for the same ticker so that new snapshot filenames (e.g. with
    a refined timestamp) do not prevent cache reuse when the content is
    unchanged.
    """

    # Explicitly bypass cache when forced so callers can see the reason in logs
    if force:
        logger.info("force refresh requested for %s; bypassing snapshot cache", ticker)
        return None

    key = str(snapshot_path.resolve())
    entry = cache_file.get(key)
    if entry and entry.get("sha256") == checksum:
        hit_path = key
    else:
        hit = _lookup_cache_by_ticker_and_checksum(cache_file, ticker, checksum)
        if hit is not None:
            hit_path, entry = hit
        else:
            hit_path = None

    if not entry or entry.get("sha256") != checksum or hit_path is None:
        # no previous snapshot or checksum mismatch -> miss
        return None

    _cache_result: Dict[str, Any] = {
        "status": "success",
        "cached": True,
        "rows_processed": 0,
        "reason": "checksum_match",
        "snapshot_path": hit_path,
        "checksum": checksum,
    }

    if ttl <= 0:
        logger.info("snapshot cache hit for %s (ttl=no-expiry)", ticker)
        return _cache_result

    processed_at = entry.get("processed_at")
    if not isinstance(processed_at, str):
        logger.warning(
            "invalid 'processed_at' in snapshot cache for %s: %r; "
            "treating as cache miss",
            ticker,
            processed_at,
        )
        return None

    try:
        last_ts = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last_ts).total_seconds()
        if age < ttl:
            logger.info(
                "snapshot cache hit for %s (age=%.1fs < ttl=%.1fs)", ticker, age, ttl
            )
            _cache_result["reason"] = "within_ttl"
            return _cache_result
    except ValueError as exc:  # parse errors only
        logger.warning(
            "invalid 'processed_at' in snapshot cache for %s: %r (%s); "
            "treating as cache miss",
            ticker,
            processed_at,
            exc,
        )
    return None


def _write_and_record_snapshot(
    df: pd.DataFrame,
    ticker: str,
    snapshot_dir: Path,
    ts: str,
) -> tuple[str, Path]:
    """Write a versioned snapshot CSV to disk.

    The filename is derived from a sanitized version of *ticker* and the
    provided timestamp *ts* (e.g. ``TICKER-YYYYMMDD.csv``).

    The actual write and pruning of old snapshots is delegated to
    :func:`src.etl.snapshot.write_snapshot`.

    Snapshot metadata (checksum, processed time, etc.) is maintained in a
    file-backed snapshot cache, not in the database.

    Invariants / caller expectations:
    - *ticker* is sanitized to allow only alphanumerics, ``-`` and ``_``; all
      other characters are replaced with ``_``.
    - *snapshot_dir* is resolved to an absolute path, and the resolved output
      path is verified to be inside that directory via ``Path.is_relative_to``.

    Returns:
        A tuple of ``(checksum, path_to_written_snapshot)``.
    """
    from src.etl.snapshot import write_snapshot

    out_path = _safe_snapshot_path(ticker, snapshot_dir, ts)

    # write_snapshot also handles pruning old files via _prune_old_snapshots
    sha = write_snapshot(df, out_path)

    # NOTE: snapshot metadata is no longer persisted to the database.
    # The cache layer is file-backed and contains the information needed
    # to avoid reprocessing unchanged snapshots.
    return sha, out_path


def _write_snapshot_file(
    df: pd.DataFrame,
    ticker: str,
    snapshot_dir: Path,
    ts: str | None = None,
) -> tuple[str, Path]:
    """Write a snapshot CSV and return `(checksum, path)`.

    This wrapper exists to keep the public API stable during refactors.

    When *ts* is not provided, a timestamp (YYYYMMDD) corresponding to the
    current UTC date is used. The ingestion pipeline passes an explicit
    timestamp to avoid races around midnight.
    """

    if ts is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")

    return _write_and_record_snapshot(df, ticker, snapshot_dir, ts)


def _run_incremental_ingest(
    df: pd.DataFrame,
    ticker: str,
    db_path: Optional[str],
) -> int:
    """Diff *df* against existing DB rows and persist only new/changed rows."""
    import src.db as _db

    try:
        existing = _db.read_prices(ticker, db_path=db_path)
    except (sqlite3.DatabaseError, FileNotFoundError):
        # common benign failures: missing DB file or corrupted database
        existing = None
    except Exception:  # pragma: no cover - propagate unexpected errors
        raise

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
        cache_file_path = _get_snapshot_cache_file(resolved_dir)

        # Use a single timestamp for this run to avoid pathological cases where
        # the process crosses midnight between cache lookup and snapshot write.
        now = datetime.now(timezone.utc)
        # Include time-of-day with microseconds to avoid collisions in
        # snapshot filenames and cache keys when multiple runs occur rapidly.
        ts = now.strftime("%Y%m%dT%H%M%S%fZ")

        # Ensure cache operations are coordinated, since the cache file is shared
        # across tickers and processes. Hold the lock only for the cache lookup
        # and the brief cache update, but not for the potentially slow
        # snapshot write + DB ingest steps.
        from src.ingest.cache import cache_file_lock

        with cache_file_lock(cache_file_path):
            cache_file = _load_snapshot_cache(cache_file_path)

            snapshot_path = _snapshot_path_for_ticker(ticker, resolved_dir, ts)
            cache_result = _check_cache_hit(
                cache_file,
                snapshot_path,
                checksum,
                resolved_ttl,
                resolved_force,
                ticker,
            )
            if cache_result is not None:
                # include duration for the quick-cached path
                elapsed = time.monotonic() - start
                cache_result["duration"] = f"{elapsed:.2f}s"
                return cache_result

        # The cache is no longer locked here; doing the write and ingest can
        # take time and should not block other tickers.
        sha, out_path = _write_snapshot_file(df, ticker, resolved_dir, ts)
        rows_processed = _run_incremental_ingest(df, ticker, resolved_db)

        # Update cache for future runs.
        # Use the same timestamp used to generate the snapshot filename
        # to avoid inconsistencies when execution crosses midnight.
        with cache_file_lock(cache_file_path):
            cache_file = _load_snapshot_cache(cache_file_path)
            cache_file[str(out_path.resolve())] = {
                "sha256": sha,
                "ticker": ticker,
                "processed_at": now.isoformat(),
            }
            # Do not persist transient auxiliary index state.
            if isinstance(cache_file.get("__meta__"), dict):
                cache_file["__meta__"].pop("snapshot_index", None)
                if not cache_file["__meta__"]:
                    cache_file.pop("__meta__", None)
            save_cache(cache_file_path, cache_file)

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
