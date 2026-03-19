"""Utilities for health and metrics reporting.

This module centralizes helper functions used by the CLI commands
`main health` and `main metrics`.

It is intended to replace the legacy `src/health.py` module while keeping
backwards compatibility (via a thin shim in `src/health.py`).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ingest.raw_storage import DEFAULT_METADATA

DEFAULT_INGEST_LOG_NAME = "ingest_logs.jsonl"


def resolve_ingest_log_path(ingest_log_path: Optional[str]) -> str:
    """Resolve a path to the ingest audit log file.

    Parameters
    ----------
    ingest_log_path:
        Optional explicit path provided by the CLI.

    Notes
    -----
    This helper accepts directory-like values as well as file paths.
    When a directory is provided (or no extension is present), the canonical
    filename ``ingest_logs.jsonl`` is appended.
    """

    raw = ingest_log_path or os.getenv("INGEST_LOG_PATH")
    if not raw:
        return str(DEFAULT_METADATA)

    path = Path(raw)

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


def _parse_iso_dt(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


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

    return _build_health_metrics_summary(logs, threshold_seconds, now)


def _build_health_metrics_summary(
    logs: List[Dict[str, Any]],
    threshold_seconds: int,
    now: datetime,
) -> Dict[str, Any]:
    """Internal helper to compute the health summary (split for complexity)."""

    last_finished: Optional[datetime] = None
    errors_last_24h = 0
    jobs_last_24h = 0
    latency_values: List[float] = []

    for rec in logs:
        finished = rec.get("finished_at") or rec.get("created_at")
        finished_dt = _parse_iso_dt(finished) if isinstance(finished, str) else None
        if finished_dt is None:
            continue

        if last_finished is None or finished_dt > last_finished:
            last_finished = finished_dt

        delta = now - finished_dt
        if delta.total_seconds() <= 24 * 3600:
            jobs_last_24h += 1
            if rec.get("status") != "success":
                errors_last_24h += 1

        duration = rec.get("duration")
        if isinstance(duration, (int, float)):
            latency_values.append(float(duration))
        elif isinstance(duration, str) and duration.endswith("s"):
            try:
                latency_values.append(float(duration[:-1]))
            except Exception:
                pass

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


def check_paths_health(paths: Dict[str, str]) -> Dict[str, Any]:
    """Check the health of a set of filesystem paths.

    Returns a dict with status and reasons for failures.
    """

    status = "ok"
    reasons: List[str] = []

    for name, path_str in paths.items():
        path = Path(path_str)
        if not path.exists():
            status = "warn" if status == "ok" else status
            reasons.append(f"{name} missing: {path}")
            continue
        if name == "db" and path.is_file():
            try:
                # Ensure we can open the file in read-only mode.
                with open(path, "rb"):
                    pass
            except Exception as exc:
                status = "error"
                reasons.append(f"db unreadable: {exc}")
            try:
                # Check owner-only permissions (600) if supported.
                mode = path.stat().st_mode & 0o777
                if mode not in (0o600, 0o644):
                    reasons.append(
                        f"db permissions are {oct(mode)} (expected 0o600 or 0o644)"
                    )
            except Exception:
                pass
        elif name != "db" and not path.is_dir():
            status = "warn" if status == "ok" else status
            reasons.append(f"{name} not a directory: {path}")

    return {"status": status, "reasons": reasons}
