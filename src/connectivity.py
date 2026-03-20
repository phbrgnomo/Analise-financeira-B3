"""Provider connectivity helpers used by the CLI.

This module encapsulates the logic for testing an adapter provider's
connectivity, keeping CLI command handlers focused on presentation and
exit codes.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TypedDict, cast

from src.adapters.factory import get_adapter
from src.utils.health import append_ingest_log_entry, get_last_success_timestamp


class ConnectionStatus(TypedDict):
    """Structured result returned by :func:`test_provider_connection`."""

    status: str
    provider: str
    latency_ms: float
    last_success_at: Optional[str]
    error: Optional[str]


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

    # `payload` is used to optionally capture additional metadata returned by
    # adapter implementations (e.g. latency_ms).
    payload: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None

    try:
        adapter = get_adapter(provider)
        check_fn = getattr(adapter, "check_connection", None)
        if callable(check_fn):
            payload = cast(Dict[str, Any], check_fn(timeout=timeout))
            status = payload.get("status", "failure")
            error = payload.get("error")

            # Prefer adapter-provided latency if available; fall back to wrapper timing.
            if isinstance(payload, dict):
                raw_latency = payload.get("latency_ms")
                if raw_latency is not None:
                    try:
                        latency_ms = float(raw_latency)
                    except (TypeError, ValueError):
                        latency_ms = None
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

    if latency_ms is None:
        duration = time.monotonic() - start
        latency_ms = round(duration * 1000, 2)

    last_success = get_last_success_timestamp(provider)

    result: ConnectionStatus = {
        "status": status,
        "provider": provider,
        "latency_ms": latency_ms,
        "last_success_at": last_success,
        "error": error,
    }

    # Log failures to ingest log for observability.
    if status != "success":
        append_ingest_log_entry(
            {
                "job_id": str(uuid.uuid4()),
                "provider": provider,
                "status": status,
                "error": error,
                "created_at": (
                    datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                ),
            }
        )

    return result
