"""
Métricas e observabilidade para operações de retry.

Coleta e expõe métricas sobre tentativas, sucessos e falhas de retry
para monitoramento e debugging de adaptadores.
"""

import threading
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RetryMetrics:
    """
    Métricas agregadas de operações de retry.

    Thread-safe para uso concorrente em múltiplos adaptadores.

    Attributes:
        retry_count: Número total de retries executados (tentativas > 1)
        success_after_retry: Sucessos obtidos após pelo menos um retry
        permanent_failures: Falhas permanentes após esgotar max_attempts
        first_attempt_success: Operações bem-sucedidas na primeira tentativa
        total_attempts: Número total de tentativas (incluindo primeiras)
    """

    retry_count: int = 0
    success_after_retry: int = 0
    permanent_failures: int = 0
    first_attempt_success: int = 0
    total_attempts: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_attempt(self) -> None:
        """Registra uma tentativa individual."""
        with self._lock:
            self.total_attempts += 1

    def record_retry(self) -> None:
        """Registra que um retry foi necessário (tentativa > 1)."""
        with self._lock:
            self.retry_count += 1

    def record_success_after_retry(self) -> None:
        """Registra sucesso após pelo menos um retry."""
        with self._lock:
            self.success_after_retry += 1

    def record_first_attempt_success(self) -> None:
        """Registra sucesso na primeira tentativa (sem retry)."""
        with self._lock:
            self.first_attempt_success += 1

    def record_permanent_failure(self) -> None:
        """Registra falha permanente após esgotar tentativas."""
        with self._lock:
            self.permanent_failures += 1

    def to_dict(self) -> Dict[str, int]:
        """
        Retorna snapshot das métricas como dicionário.

        Returns:
            Dict com todas as métricas atuais
        """
        with self._lock:
            return {
                "retry_count": self.retry_count,
                "success_after_retry": self.success_after_retry,
                "permanent_failures": self.permanent_failures,
                "first_attempt_success": self.first_attempt_success,
                "total_attempts": self.total_attempts,
            }

    def reset(self) -> None:
        """Reseta todas as métricas para zero (útil para testes)."""
        with self._lock:
            self.retry_count = 0
            self.success_after_retry = 0
            self.permanent_failures = 0
            self.first_attempt_success = 0
            self.total_attempts = 0


# Instância global de métricas (singleton thread-safe)
_global_metrics = RetryMetrics()


def get_global_metrics() -> RetryMetrics:
    """
    Retorna instância global de métricas.

    Returns:
        RetryMetrics singleton compartilhado por todos os adaptadores
    """
    return _global_metrics
