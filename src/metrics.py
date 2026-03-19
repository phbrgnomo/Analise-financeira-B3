"""Legacy metrics helper.

This module is maintained for backward compatibility. The active implementation
is located in ``src/utils/metrics_prometheus.py``.
"""

from __future__ import annotations

from src.utils.metrics_prometheus import (
    get_counter,
    get_histogram,
    increment_counter,
    observe_histogram,
    start_metrics_server,
)

__all__ = [
    "get_counter",
    "get_histogram",
    "increment_counter",
    "observe_histogram",
    "start_metrics_server",
]
