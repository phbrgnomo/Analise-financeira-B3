"""Utilities for health and metrics reporting.

This module centralizes helper functions used by the CLI commands
`main health` and `main metrics`.

It is intended to replace the legacy `src/health.py` module while keeping
backwards compatibility (via a thin shim in `src/health.py`).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ingest.raw_storage import DEFAULT_METADATA

__all__ = [
    "resolve_ingest_log_path",
    "read_ingest_logs",
    "get_last_success_timestamp",
    "append_ingest_log_entry",
    "compute_health_metrics",
    "check_paths_health",
    "DEFAULT_INGEST_LOG_NAME",
]

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

    # Resolve order of precedence: explicit CLI arg, env var, then default.
    raw = ingest_log_path or os.getenv("INGEST_LOG_PATH") or str(DEFAULT_METADATA)

    # Support directory-like values (or values without an extension) by appending
    # the canonical filename.
    path = Path(raw)
    if raw.endswith(("/", os.sep)) or not path.suffix:
        path = path / DEFAULT_INGEST_LOG_NAME

    return str(path)


def read_ingest_logs(path: str) -> List[Dict[str, Any]]:
    """Read an ingest audit log file (JSONL) into a list of dicts.

    Returns an empty list if the path does not exist.
    Blank lines are ignored, and any line that fails JSON parsing is skipped.

    Parameters
    ----------
    path:
        Path to a JSONL file (one JSON object per line).

    Returns
    -------
    List[Dict[str, Any]]
        Parsed log entries.
    """

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


def get_last_success_timestamp(
    provider: str,
    ingest_log_path: Optional[str] = None,
) -> Optional[str]:
    """Return the latest successful ingestion timestamp for a provider.

    This is a convenience wrapper around ``read_ingest_logs`` that filters for
    successful entries for a given provider and returns the most recent
    ``created_at``/``finished_at`` timestamp in normalized ISO8601 format.
    """

    path = resolve_ingest_log_path(ingest_log_path)
    records = read_ingest_logs(path)

    latest: Optional[datetime] = None
    for rec in records:
        if rec.get("provider") != provider:
            continue
        if rec.get("status") != "success":
            continue
        created = rec.get("created_at") or rec.get("finished_at")
        if not created:
            continue
        dt = _parse_iso_dt(created)
        if dt is None:
            continue
        if latest is None or dt > latest:
            latest = dt

    if latest is None:
        return None

    # Preserve the original timezone when present; if absent, assume UTC.
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    return latest.isoformat().replace("+00:00", "Z")


def append_ingest_log_entry(
    entry: Dict[str, Any],
    ingest_log_path: Optional[str] = None,
) -> None:
    """Append a JSONL record to the ingest logs file.

    This is a small helper that ensures the containing directory exists and
    will not raise on failures, mirroring the existing behavior in
    :mod:`src.connectivity`.
    """

    try:
        path = resolve_ingest_log_path(ingest_log_path)
        if dirpath := os.path.dirname(path):
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logging.getLogger(__name__).exception("failed to write ingest log entry")


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
        # Ignore future-dated records; only count strictly past 24h.
        if 0 <= delta.total_seconds() <= 24 * 3600:
            jobs_last_24h += 1
            if rec.get("status") != "success":
                errors_last_24h += 1

        duration = rec.get("duration")
        if isinstance(duration, (int, float)):
            latency_values.append(float(duration))
        elif isinstance(duration, str):
            # Support both legacy format (numeric string) and '1.23s' suffix.
            with contextlib.suppress(Exception):
                duration_val = (
                    float(duration[:-1]) if duration.endswith("s") else float(duration)
                )
                latency_values.append(duration_val)
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
        if name == "db" and path.is_file():
            try:
                # Ensure we can open the file in read-only mode.
                with open(path, "rb"):
                    pass
            except Exception as exc:
                status = "error"
                reasons.append(f"db unreadable: {exc}")
            with contextlib.suppress(Exception):
                # Best-effort permission check:
                # warn only on clearly too-permissive modes.
                mode = path.stat().st_mode & 0o777
                # World-writable or group-writable and world-readable are suspicious.
                if mode & 0o002 or mode & 0o004 and mode & 0o020:
                    reasons.append(
                        f"db permissions are {oct(mode)}; "
                        "file may be too broadly accessible"
                    )
        elif name == "db":
            # If we were asked to check a database path, it must exist and be a file.
            status = "error"
            if not path.exists():
                reasons.append(f"db missing: {path}")
            elif not path.is_file():
                reasons.append(f"db is not a file: {path}")
        elif name != "db" and not path.is_dir():
            status = "warn" if status == "ok" else status
            reasons.append(f"{name} not a directory: {path}")

    return {"status": status, "reasons": reasons}
