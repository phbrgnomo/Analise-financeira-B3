"""Lightweight Prometheus metrics wrapper with optional dependency.

This module provides no-op implementations when `prometheus_client` is not
installed so tests and minimal environments don't require the package.
"""

import threading
from typing import Any, Dict, Protocol, cast, runtime_checkable

from src.logging_config import get_logger

logger = get_logger(__name__)


@runtime_checkable
class Metric(Protocol):
    """Interface for Prometheus-style metrics."""

    def inc(self, amount: float = 1.0) -> Any: ...

    def observe(self, value: float) -> Any: ...


_HAS_PROM = False
try:
    from prometheus_client import Counter, Histogram, start_http_server  # type: ignore

    _HAS_PROM = True
except ImportError:
    # prometheus_client not available; fall back to no-op
    Counter: Any = None  # type: ignore
    Histogram: Any = None  # type: ignore
    start_http_server: Any = None  # type: ignore


class _NoopMetric:
    """No-op metric implementation used when metrics are disabled.

    This implementation is returned when `prometheus_client` is not available,
    ensuring callers can safely call `inc()` and `observe()` without errors.
    """

    def inc(self, *args: Any, **kwargs: Any) -> None:
        return None

    def observe(self, *args: Any, **kwargs: Any) -> None:
        return None


_counters: Dict[str, Metric] = {}
_histograms: Dict[str, Metric] = {}
_metrics_lock = threading.Lock()


def get_counter(name: str, documentation: str = "") -> Metric:
    """Return a counter-like metric for the given name."""

    if not _HAS_PROM:
        return _NoopMetric()

    with _metrics_lock:
        if name not in _counters:
            assert Counter is not None
            _counters[name] = cast(Metric, Counter(name, documentation))
        return _counters[name]


def get_histogram(name: str, documentation: str = "") -> Metric:
    """Return a histogram-like metric for the given name."""

    if not _HAS_PROM:
        return _NoopMetric()

    with _metrics_lock:
        if name not in _histograms:
            assert Histogram is not None
            _histograms[name] = cast(Metric, Histogram(name, documentation))
        return _histograms[name]


def increment_counter(name: str, amount: float = 1.0) -> None:
    """Increment a named counter metric."""

    try:
        get_counter(name).inc(amount)
    except Exception:
        logger.debug("metrics increment failed", exc_info=True)


def observe_histogram(name: str, value: float) -> None:
    """Observe a value for a named histogram metric."""

    try:
        get_histogram(name).observe(value)
    except Exception:
        logger.debug("metrics observe failed", exc_info=True)


def start_metrics_server(port: int = 8000) -> None:
    """Start an HTTP server exposing Prometheus metrics."""

    if not _HAS_PROM or start_http_server is None:
        msg = "prometheus_client not available; metrics server not started"
        logger.info(msg)
        return
    try:
        start_http_server(port)
        logger.info("Prometheus metrics server started", extra={"port": port})
    except Exception:
        logger.exception("failed to start Prometheus metrics server")
