"""Provider connectivity helpers used by the CLI.

This module encapsulates the logic for testing an adapter provider's
connectivity, keeping CLI command handlers focused on presentation and
exit codes.
"""

from __future__ import annotations

import logging
import time

from src.adapters.factory import get_adapter


def test_provider_connection(provider: str) -> dict[str, object]:
    """Test connectivity for a provider and return a normalized status dict."""

    start = time.monotonic()
    status = "failure"
    error = None

    try:
        adapter = get_adapter(provider)
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
        logging.exception("error testing provider %s", provider)
        error = str(exc)

    duration = time.monotonic() - start
    return {
        "status": status,
        "provider": provider,
        "latency_ms": round(duration * 1000, 2),
        "error": error,
    }
