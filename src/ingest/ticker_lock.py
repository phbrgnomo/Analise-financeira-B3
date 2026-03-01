"""Lock intra-processo por ticker para serializar operações de ingestão.

Este módulo evita que múltiplas threads no mesmo processo executem ingestão
simultânea para o mesmo ticker, reduzindo risco de corridas entre escrita de
snapshot, leitura incremental e upsert no SQLite.

Nota
----
A sincronização está limitada ao processo atual. Dois comandos Python
separados (por exemplo, dois invocados em terminais distintos) não serão
sincronizados por este módulo. Para esse caso é preciso implementar um bloqueio
baseado em arquivo ou usar outra forma de exclusão mútua entre processos.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

_registry_lock = threading.Lock()
_ticker_locks: dict[str, threading.Lock] = {}


def _normalized_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _get_lock(ticker: str) -> threading.Lock:
    key = _normalized_ticker(ticker)
    with _registry_lock:
        lock = _ticker_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _ticker_locks[key] = lock
        return lock


@contextmanager
def lock_ticker(ticker: str):
    """Serializa seção crítica para o ticker informado."""
    lock = _get_lock(ticker)
    # use lock as a context manager for auto acquire/release, safer on error
    with lock:
        yield
