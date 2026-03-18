"""Simple filesystem cache for snapshot ingestion.

This module provides helpers to load/store a JSON-backed cache that records
which snapshot files have already been processed, along with their checksum
and the timestamp of the last ingestion.  The cache is intentionally very
lightweight: it assumes a single process is writing and uses atomic `os.replace`
when updating the file.

Keys are absolute paths to snapshot files (``str(Path.resolve())``) and values
are dictionaries containing ``sha256`` and ``processed_at`` (UTC ISO string).

The TTL logic lives in the orchestration layer (`src.ingest.ingest_snapshot`
which uses these utilities).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _record_cache_fallback_metric() -> None:
    """Increment the metric used when reading the snapshot cache fails.

    The metric is optional (may not be available in all environments), so
    failures are logged at debug level rather than propagated.
    """

    try:
        from src import metrics

        metrics.increment_counter("snapshot_cache_fallback")
    except Exception:  # pragma: no cover — metrics optional
        logger.debug("metrics increment failed", exc_info=True)


@contextlib.contextmanager
def cache_file_lock(path: Path):
    """Context manager that serializes access to the cache file across processes.

    The snapshot cache is shared by all tickers within the same directory, and
    concurrent ingest runs (even for different tickers) may race when updating
    the cache file.  This helper uses an OS lock file (via ``fcntl`` on Unix)
    so that only one process can read/modify/write the cache at a time.

    The lock is best-effort: on platforms where ``fcntl`` is unavailable, no
    locking is performed.
    """

    # Use a sibling lock file to avoid interfering with the cache itself.
    lock_path = path.with_suffix(path.suffix + ".lock")
    # Ensure the lock file exists (a no-op if already present).
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # We deliberately open in append mode so the file exists without truncating.
    with open(lock_path, "a+") as fh:
        try:
            import fcntl  # type: ignore

            fcntl.flock(fh, fcntl.LOCK_EX)
        except Exception:
            # If we can't lock (e.g. on Windows), proceed without locking.
            yield
            return

        try:
            yield
        finally:
            try:
                fcntl.flock(fh, fcntl.LOCK_UN)
            except Exception:
                pass


def load_cache(path: Path) -> Dict[str, Any]:
    """Return the cache dictionary stored at ``path`` or an empty dict.

    If the file does not exist or is invalid JSON the function returns an
    empty dictionary and logs a warning.
    """
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        logger.warning(
            "failed to decode JSON in snapshot cache %s; treating as empty cache",
            path,
            exc_info=True,
        )
        _record_cache_fallback_metric()
        return {}
    except OSError:
        logger.warning(
            "failed to read snapshot cache %s due to OS error; treating as empty cache",
            path,
            exc_info=True,
        )
        _record_cache_fallback_metric()
        return {}


def save_cache(path: Path, cache: Dict[str, Any]) -> None:
    """Atomically write ``cache`` to ``path``.

    The parent directory is created if necessary.  A temporary file is written
    and ``os.replace`` is used for atomicity.

    Any failure during serialization or replacement is logged and the temporary
    file is cleaned up to avoid leaving stale ``.tmp`` files behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
        os.replace(str(tmp), str(path))
    except (TypeError, ValueError, OSError):
        logger.warning(
            "failed to write snapshot cache %s; leaving existing cache file unchanged",
            path,
            exc_info=True,
        )
        # Best-effort cleanup of partially written temp file
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            logger.debug(
                "failed to remove temporary snapshot cache file %s", tmp, exc_info=True
            )


def entry_is_fresh(entry: Dict[str, Any], ttl: Optional[float]) -> bool:
    """Return ``True`` if the cache entry is still within ``ttl`` seconds.

    ``ttl`` may be fractional (tests sometimes use `0.1` seconds) so the
    type is ``float | None``.  If ``ttl`` is ``None`` the entry is always
    considered fresh.  The ``processed_at`` value is an ISO formatted UTC
    timestamp.
    """
    if ttl is None:
        return True
    try:
        # ``entry`` comes from untyped JSON so mypy/Pylance see Any | None
        ts_str: Optional[str] = entry.get("processed_at")  # narrow below
        # guard against missing/incorrect types; Pylance warns about Any | None
        if not isinstance(ts_str, str):
            # treat non-string timestamps as stale
            return False
        # mypy now understands ts_str is a ``str``
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except Exception:  # pragma: no cover - treat as stale if invalid
        return False
    age = datetime.now(timezone.utc) - ts
    return age.total_seconds() < ttl


__all__ = [
    "load_cache",
    "save_cache",
    "entry_is_fresh",
    "cache_file_lock",
]
