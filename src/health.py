"""Helper utilities for health/metrics reporting.

This module is intentionally separate from ``src/main.py`` to keep the CLI
orchestration lean and to allow reuse from other components (e.g. a web
server or monitoring job).

The health metrics are derived from the ingest audit log.
The log file is ``metadata/ingest_logs.jsonl``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.ingest.raw_storage import DEFAULT_METADATA

DEFAULT_INGEST_LOG_NAME = "ingest_logs.jsonl"


def resolve_ingest_log_path(ingest_log_path: Optional[str]) -> str:
    """Resolve a path to the ingest audit log file.

    Parameters
    ----------
    ingest_log_path:
        Optional explicit path provided by the CLI. If ``None`` the
        environment variable ``INGEST_LOG_PATH`` is checked. When neither is
        provided, ``src.ingest.raw_storage.DEFAULT_METADATA`` is used.

    Notes
    -----
    This helper is tolerant of directory paths (e.g. ``metadata/``) and will
    append the canonical filename ``ingest_logs.jsonl`` when needed. This
    prevents callers from accidentally passing a directory and then crashing
    when trying to open it as a file.
    """

    raw = ingest_log_path or os.getenv("INGEST_LOG_PATH")
    if not raw:
        return str(DEFAULT_METADATA)

    path = Path(raw)

    # Allow directory-like values (including trailing slash or missing extension) by
    # ensuring we end up with a file path. We intentionally avoid filesystem-based
    # checks (like Path.is_dir()) so that non-existent directories are treated
    # consistently based purely on the input syntax.
    if raw.endswith(("/", os.sep)) or not path.suffix:
        path = path / DEFAULT_INGEST_LOG_NAME

    return str(path)


def read_ingest_logs(path: str) -> List[Dict[str, Any]]:
    """Read an ingest audit log file (JSONL) into a list of dicts."""

    if not os.path.exists(path):
        return []

    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _parse_finished_at(rec: Dict[str, Any]) -> Optional[datetime]:
    """Parse an ISO-8601 "finished_at" timestamp into an aware datetime.

    Parameters
    ----------
    rec:
        A log record dictionary containing a "finished_at" key.

    Returns
    -------
    Optional[datetime]
        A timezone-aware datetime parsed from the string, or None if the
        field is missing or cannot be parsed.

    Notes
    -----
    The function accepts timestamps suffixed with "Z" and converts them to
    a form acceptable by ``datetime.fromisoformat``.
    """

    finished = rec.get("finished_at")
    if not finished:
        return None
    try:
        return datetime.fromisoformat(finished.replace("Z", "+00:00"))
    except Exception:
        return None


def _extract_latency(rec: Dict[str, Any]) -> Optional[float]:
    """Extract a duration value (seconds) from a log record.

    If the record has a numeric duration (int/float), it is returned as float.
    If the record has a string duration (e.g., "1.23s"), the trailing "s"
    is stripped before conversion.

    Parameters
    ----------
    rec:
        A log record dictionary.

    Returns
    -------
    Optional[float]
        The duration in seconds, or None if it cannot be parsed.
    """

    dur = rec.get("duration")
    if isinstance(dur, (int, float)):
        return float(dur)
    if not isinstance(dur, str):
        return None
    try:
        return float(dur[:-1]) if dur.endswith("s") else float(dur)
    except Exception:
        return None


def _analyze_logs(
    logs: List[Dict[str, Any]],
    now: datetime,
) -> Tuple[Optional[datetime], int, int, List[float]]:
    """Analyze log entries and extract metrics used for health computation."""

    last_finished: Optional[datetime] = None
    errors_last_24h = 0
    jobs_last_24h = 0
    latency_values: List[float] = []

    for rec in logs:
        finished_dt = _parse_finished_at(rec)
        if finished_dt is None:
            continue

        if last_finished is None or finished_dt > last_finished:
            last_finished = finished_dt

        delta = now - finished_dt
        if delta <= timedelta(hours=24):
            jobs_last_24h += 1
            if rec.get("status") != "success":
                errors_last_24h += 1

        latency = _extract_latency(rec)
        if latency is not None and latency > 0:
            latency_values.append(latency)

    return last_finished, errors_last_24h, jobs_last_24h, latency_values


def compute_health_metrics(
    logs: List[Dict[str, Any]],
    threshold_seconds: int,
) -> Dict[str, Any]:
    """Compute high-level health metrics from ingest audit log entries."""

    now = datetime.now(timezone.utc)

    if not logs:
        return {
            "status": "unknown",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "metrics": {
                "ingest_lag_seconds": None,
                "errors_last_24h": 0,
                "jobs_last_24h": 0,
                "avg_latency_seconds": None,
            },
            "thresholds": {"ingest_lag_seconds": threshold_seconds},
        }

    (
        last_finished,
        errors_last_24h,
        jobs_last_24h,
        latency_values,
    ) = _analyze_logs(logs, now)

    if last_finished is not None:
        ingest_lag = (now - last_finished).total_seconds()
    else:
        ingest_lag = float("inf")

    avg_latency = sum(latency_values) / len(latency_values) if latency_values else None

    status = _determine_health_status(ingest_lag, errors_last_24h, threshold_seconds)

    return {
        "status": status,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "metrics": {
            "ingest_lag_seconds": ingest_lag,
            "errors_last_24h": errors_last_24h,
            "jobs_last_24h": jobs_last_24h,
            "avg_latency_seconds": avg_latency,
        },
        "thresholds": {"ingest_lag_seconds": threshold_seconds},
    }


def _determine_health_status(
    ingest_lag: float, errors_last_24h: int, threshold_seconds: int
) -> str:
    """Return the health status given ingest latency and error counts."""

    status = "healthy"
    if ingest_lag > threshold_seconds:
        status = "degraded"
    if ingest_lag > threshold_seconds * 2:
        status = "unhealthy"
    if errors_last_24h > 0 and status == "healthy":
        status = "degraded"
    return status
