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
except ImportError:
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
    """Return a counter-like metric for the given name.

    Parameters
    ----------
    name : str
        Metric name (used to look up the metric cache).
    documentation : str, optional
        Documentation string for the metric (default: ``""``).

    Returns
    -------
    Counter | _NoopMetric
        When `prometheus_client` is available (`_HAS_PROM` is True), returns
        a real `Counter`. Otherwise returns a `_NoopMetric` that implements
        the same interface without side effects.

    Side effects
    ------------
    - If `_HAS_PROM` is True and the metric is not already cached, a new
      `Counter` is created and stored in `_counters`.
    - If `_HAS_PROM` is False, this is a no-op.
    """
    if not _HAS_PROM:
        return _NoopMetric()
    if name not in _counters:
        _counters[name] = Counter(name, documentation)
    return _counters[name]


def get_histogram(name: str, documentation: str = ""):
    """Return a histogram-like metric for the given name.

    Parameters
    ----------
    name : str
        Metric name (used to look up the metric cache).
    documentation : str, optional
        Documentation string for the metric (default: ``""``).

    Returns
    -------
    Histogram | _NoopMetric
        When `prometheus_client` is available (`_HAS_PROM` is True), returns
        a real `Histogram`. Otherwise returns a `_NoopMetric` that implements
        the same interface without side effects.

    Side effects
    ------------
    - If `_HAS_PROM` is True and the metric is not already cached, a new
      `Histogram` is created and stored in `_histograms`.
    - If `_HAS_PROM` is False, this is a no-op.
    """
    if not _HAS_PROM:
        return _NoopMetric()
    if name not in _histograms:
        _histograms[name] = Histogram(name, documentation)
    return _histograms[name]


def increment_counter(name: str, amount: int = 1) -> None:
    """Increment a named counter metric.

    Parameters
    ----------
    name : str
        Metric name.
    amount : int
        Amount to increment the counter by.

    Notes
    -----
    If Prometheus is not installed, this is a no-op. Exceptions during
    metric updates are logged at debug level.
    """
    try:
        get_counter(name).inc(amount)
    except Exception:
        logger.debug("metrics increment failed", exc_info=True)


def observe_histogram(name: str, value: float) -> None:
    """Observe a value for a named histogram metric.

    Parameters
    ----------
    name : str
        Metric name.
    value : float
        Value to observe.

    Notes
    -----
    If Prometheus is not installed, this is a no-op. Exceptions during
    metric updates are logged at debug level.
    """
    try:
        get_histogram(name).observe(value)
    except Exception:
        logger.debug("metrics observe failed", exc_info=True)


def start_metrics_server(port: int = 8000) -> None:
    """Start an HTTP server exposing Prometheus metrics.

    Parameters
    ----------
    port : int
        TCP port to bind the metrics endpoint to (default: 8000).

    Notes
    -----
    If ``prometheus_client`` is not installed, this is a no-op.
    """
    if not _HAS_PROM or start_http_server is None:
        msg = "prometheus_client not available; metrics server not started"
        logger.info(msg)
        return
    try:
        start_http_server(port)
        logger.info("Prometheus metrics server started", extra={"port": port})
    except Exception:
        logger.exception("failed to start Prometheus metrics server")
