"""Legacy health helpers.

This module is maintained for backwards compatibility.  The active
implementation lives in ``src/utils/health.py``.
"""

from __future__ import annotations

from src.utils.health import (
    append_ingest_log_entry,
    compute_health_metrics,
    get_last_success_timestamp,
    read_ingest_logs,
    resolve_ingest_log_path,
)

__all__ = [
    "compute_health_metrics",
    "read_ingest_logs",
    "resolve_ingest_log_path",
    "get_last_success_timestamp",
    "append_ingest_log_entry",
]
