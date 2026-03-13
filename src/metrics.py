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
        Nome da métrica (usado para registrar/recuperar do cache).
    documentation : str, optional
        Texto descritivo da métrica (padrão: "").

    Returns
    -------
    Counter | _NoopMetric
        Quando `prometheus_client` estiver disponível (`_HAS_PROM is True`),
        retorna uma instância de `Counter` (do cliente Prometheus). Caso o
        pacote não esteja disponível, retorna um `_NoopMetric` que aceita as
        mesmas chamadas (`inc`) sem efeitos colaterais.

    Side effects
    ------------
    - Se `_HAS_PROM` for True e a métrica não existir em `_counters`, a
      função cria e armazena uma nova `Counter` em `_counters` sob a chave
      `name`.
    - Se `_HAS_PROM` for False, nenhum registro é criado e a função é
      efetivamente um no-op.
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
        Nome da métrica (usado para registrar/recuperar do cache).
    documentation : str, optional
        Texto descritivo da métrica (padrão: "").

    Returns
    -------
    Histogram | _NoopMetric
        Quando `prometheus_client` estiver disponível (`_HAS_PROM is True`),
        retorna uma instância de `Histogram` (do cliente Prometheus). Caso o
        pacote não esteja disponível, retorna um `_NoopMetric` que aceita as
        mesmas chamadas (`observe`) sem efeitos colaterais.

    Side effects
    ------------
    - Se `_HAS_PROM` for True e a métrica não existir em `_histograms`, a
      função cria e armazena uma nova `Histogram` em `_histograms` sob a chave
      `name`.
    - Se `_HAS_PROM` for False, nenhum registro é criado e a função é
      efetivamente um no-op.
    """
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
        msg = "prometheus_client não disponível; servidor de métricas não iniciado"
        logger.info(msg)
        return
    try:
        start_http_server(port)
        logger.info("servidor de métricas Prometheus iniciado", extra={"port": port})
    except Exception:
        logger.exception("falha ao iniciar o servidor de métricas Prometheus")
