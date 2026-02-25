"""Lightweight Prometheus metrics wrapper with optional dependency.

This module provides no-op implementations when `prometheus_client` is not
installed so tests and minimal environments don't require the package.
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)

_HAS_PROM = False
try:
    from prometheus_client import Counter, Histogram, start_http_server

    _HAS_PROM = True
except Exception:
    # prometheus_client not available; fall back to no-op
    Counter = None  # type: ignore
    Histogram = None  # type: ignore
    start_http_server = None  # type: ignore


class _NoopMetric:
    def inc(self, *_, **__):
        return None

    def observe(self, *_, **__):
        return None


_counters: Dict[str, object] = {}
_histograms: Dict[str, object] = {}


def get_counter(name: str, documentation: str = ""):
    if not _HAS_PROM:
        return _NoopMetric()
    if name not in _counters:
        _counters[name] = Counter(name, documentation)
    return _counters[name]


def get_histogram(name: str, documentation: str = ""):
    if not _HAS_PROM:
        return _NoopMetric()
    if name not in _histograms:
        _histograms[name] = Histogram(name, documentation)
    return _histograms[name]


def increment_counter(name: str, amount: int = 1) -> None:
    try:
        get_counter(name).inc(amount)
    except Exception:
        logger.debug("metrics increment failed", exc_info=True)


def observe_histogram(name: str, value: float) -> None:
    try:
        get_histogram(name).observe(value)
    except Exception:
        logger.debug("metrics observe failed", exc_info=True)


def start_metrics_server(port: int = 8000) -> None:
    if not _HAS_PROM or start_http_server is None:
        logger.info("prometheus_client not available; metrics server not started")
        return
    try:
        start_http_server(port)
        logger.info("prometheus metrics server started", extra={"port": port})
    except Exception:
        logger.exception("failed to start prometheus metrics server")
