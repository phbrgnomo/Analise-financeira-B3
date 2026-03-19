"""Provider connectivity helpers used by the CLI.

This module encapsulates the logic for testing an adapter provider's
connectivity, keeping CLI command handlers focused on presentation and
exit codes.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TypedDict

from src.adapters.factory import get_adapter
from src.health import read_ingest_logs, resolve_ingest_log_path


class ConnectionStatus(TypedDict):
    """Structured result returned by :func:`test_provider_connection`."""

    status: str
    provider: str
    latency_ms: float
    last_success_at: Optional[str]
    error: Optional[str]


def _last_success_timestamp(
    provider: str,
    ingest_log_path: Optional[str] = None,
) -> Optional[str]:
    """Return the last successful connection timestamp for a provider.

    The function looks for the most recent record in the ingest log where
    ``status == 'success'`` and ``provider`` matches. It returns the
    ``created_at`` field in ISO8601 format when available.
    """

    try:
        path = resolve_ingest_log_path(ingest_log_path)
        records = read_ingest_logs(path)
    except Exception:
        return None

    latest: Optional[datetime] = None
    for rec in records:
        if rec.get("provider") != provider:
            continue
        if rec.get("status") != "success":
            continue
        created = rec.get("created_at") or rec.get("finished_at")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            continue
        if latest is None or dt > latest:
            latest = dt

    if latest is None:
        return None

    return latest.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _append_ingest_log_entry(
    entry: Dict[str, Any],
    ingest_log_path: Optional[str] = None,
) -> None:
    """Append a single JSON record to the ingest log file (JSONL)."""

    try:
        path = resolve_ingest_log_path(ingest_log_path)
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logging.getLogger(__name__).exception("failed to write ingest log entry")


def test_provider_connection(
    provider: str,
    timeout: Optional[float] = None,
) -> ConnectionStatus:
    """Test provider connectivity and return a normalized status dict.

    Parameters
    ----------
    provider:
        Name of the provider/adapter to test (e.g., "yfinance", "dummy").
    timeout:
        Optional timeout in seconds for the check.

    Returns
    -------
    ConnectionStatus
        A structured dict describing the provider health check result.
    """

    start = time.monotonic()
    status = "failure"
    error: Optional[str] = None

    try:
        adapter = get_adapter(provider)
        check_fn = getattr(adapter, "check_connection", None)
        if callable(check_fn):
            payload = check_fn(timeout=timeout)
            status = payload.get("status", "failure")
            error = payload.get("error")
        else:
            # Fallback to legacy boolean health check.
            test_connection = getattr(adapter, "test_connection", None)
            if callable(test_connection):
                healthy = test_connection()
                status = "success" if healthy else "failure"
            elif provider == "dummy":
                status = "success"
            else:
                status = "failure"
                error = "provider does not support test-conn"
    except Exception as exc:
        status = "failure"
        logging.getLogger(__name__).exception("error testing provider %s", provider)
        error = str(exc)

    duration = time.monotonic() - start
    last_success = _last_success_timestamp(provider)

    result: ConnectionStatus = {
        "status": status,
        "provider": provider,
        "latency_ms": round(duration * 1000, 2),
        "last_success_at": last_success,
        "error": error,
    }

    # Log failures to ingest log for observability.
    if status != "success":
        _append_ingest_log_entry(
            {
                "job_id": None,
                "provider": provider,
                "status": status,
                "error": error,
                "created_at": datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                ),
            }
        )

    return result
