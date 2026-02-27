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

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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
        return {}
    except OSError:
        logger.warning(
            "failed to read snapshot cache %s due to OS error; treating as empty cache",
            path,
            exc_info=True,
        )
        return {}


def save_cache(path: Path, cache: Dict[str, Any]) -> None:
    """Atomically write ``cache`` to ``path``.

    The parent directory is created if necessary.  A temporary file is written
    and ``os.replace`` is used for atomicity.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False)
    os.replace(str(tmp), str(path))


def entry_is_fresh(entry: Dict[str, Any], ttl: Optional[int]) -> bool:
    """Return ``True`` if the cache entry is still within ``ttl`` seconds.

    If ``ttl`` is ``None`` the entry is always considered fresh.  The
    ``processed_at`` value is an ISO formatted UTC timestamp.
    """
    if ttl is None:
        return True
    try:
        ts = datetime.fromisoformat(entry.get("processed_at"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except Exception:  # pragma: no cover - treat as stale if invalid
        return False
    age = datetime.now(timezone.utc) - ts
    return age.total_seconds() < ttl


__all__ = ["load_cache", "save_cache", "entry_is_fresh"]
