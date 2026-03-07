#!/usr/bin/env python3
"""scripts/test_retry_backoff.py

Demonstração simples do mecanismo de retry/backoff implementado em
`src/adapters/base.py` usando um adaptador fictício que falha N vezes
antes de retornar sucesso. Usa `RetryConfig` para acelerar delays
durante o teste e imprime métricas coletadas em `retry_metrics`.

Uso:
    python scripts/test_retry_backoff.py
"""

import time
from typing import Optional

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.retry_config import RetryConfig
from src.adapters.retry_metrics import get_global_metrics


class FlakyAdapter(Adapter):
    """Adaptador de teste que falha nas primeiras N chamadas de _fetch_once."""

    def __init__(self, fail_times: int = 2, retry_config: Optional[RetryConfig] = None):
        super().__init__(retry_config=retry_config)
        self._fail_times = fail_times
        self._calls = 0

    def fetch(
        self,
        ticker: str,
        start: str = "",
        end: str = "",
        **kwargs,
    ) -> pd.DataFrame:
        # Expor a API pública como os adaptadores reais
        return self._fetch_with_retries(ticker, start, end, **kwargs)

    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        self._calls += 1
        print(f"_fetch_once called (attempt={self._calls})")
        # Simula erro de rede nas primeiras N chamadas
        if self._calls <= self._fail_times:
            raise ConnectionError("simulated transient network error")

        # Retorna um DataFrame simples como sucesso
        dates = pd.date_range("2024-01-01", periods=1)
        return pd.DataFrame(
            {
                "Open": [1],
                "High": [1],
                "Low": [1],
                "Close": [1],
                "Adj Close": [1],
                "Volume": [1],
            },
            index=dates,
        )


def main():
    # Configuração de retry com delays reduzidos para demo rápida
    rc = RetryConfig(
        max_attempts=5,
        initial_delay_ms=50,
        max_delay_ms=500,
        backoff_factor=2.0,
        timeout_seconds=10,
    )

    metrics = get_global_metrics()
    metrics.reset()

    adapter = FlakyAdapter(fail_times=2, retry_config=rc)

    print("Starting demo fetch with retry/backoff")
    start_time = time.time()
    try:
        df = adapter.fetch("TEST", start="2024-01-01", end="2024-01-01")
        print("Fetch succeeded, rows:", len(df))
    except Exception as e:
        print("Fetch failed:", type(e).__name__, e)
    elapsed = time.time() - start_time

    print("Elapsed time: {:.3f}s".format(elapsed))
    print("Retry metrics:", metrics.to_dict())


if __name__ == "__main__":
    main()
