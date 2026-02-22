"""
Configuração de retry/backoff para adaptadores.

Define parâmetros configuráveis via variáveis de ambiente para
controle granular de políticas de retry em chamadas a APIs externas.
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class RetryConfig:
    """
    Configuração de retry com backoff exponencial.

    Attributes:
        max_attempts: Número máximo de tentativas (incluindo a primeira)
        initial_delay_ms: Delay inicial em milissegundos
        max_delay_ms: Delay máximo em milissegundos (cap para backoff)
        backoff_factor: Fator multiplicativo para backoff exponencial
        retry_on_status_codes: Lista de códigos HTTP que devem acionar retry
        timeout_seconds: Timeout total para operação em segundos
    """

    max_attempts: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    backoff_factor: float = 2.0
    retry_on_status_codes: List[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls, prefix: str = "ADAPTER_RETRY") -> "RetryConfig":
        """
        Carrega configuração de variáveis de ambiente.

        Args:
            prefix: Prefixo das variáveis de ambiente (padrão: ADAPTER_RETRY)

        Variáveis de ambiente suportadas:
            - {prefix}_MAX_ATTEMPTS: número máximo de tentativas
            - {prefix}_INITIAL_DELAY_MS: delay inicial em ms
            - {prefix}_MAX_DELAY_MS: delay máximo em ms
            - {prefix}_BACKOFF_FACTOR: fator de backoff
            - {prefix}_ON_STATUS_CODES: códigos HTTP separados por vírgula
            - {prefix}_TIMEOUT_SECONDS: timeout em segundos

        Returns:
            RetryConfig com valores carregados do ambiente ou padrões
        """
        return cls(
            max_attempts=int(os.getenv(f"{prefix}_MAX_ATTEMPTS", "3")),
            initial_delay_ms=int(os.getenv(f"{prefix}_INITIAL_DELAY_MS", "1000")),
            max_delay_ms=int(os.getenv(f"{prefix}_MAX_DELAY_MS", "30000")),
            backoff_factor=float(os.getenv(f"{prefix}_BACKOFF_FACTOR", "2.0")),
            retry_on_status_codes=cls._parse_status_codes(
                os.getenv(f"{prefix}_ON_STATUS_CODES", "429,500,502,503,504")
            ),
            timeout_seconds=int(os.getenv(f"{prefix}_TIMEOUT_SECONDS", "30")),
        )

    @staticmethod
    def _parse_status_codes(codes_str: str) -> List[int]:
        """Parse string de códigos HTTP separados por vírgula."""
        try:
            return [int(code.strip()) for code in codes_str.split(",") if code.strip()]
        except ValueError:
            # Retornar padrões seguros se parsing falhar
            return [429, 500, 502, 503, 504]

    def compute_delay_ms(self, attempt: int) -> int:
        """
        Calcula delay em milissegundos para uma tentativa usando backoff exponencial.

        Args:
            attempt: Número da tentativa (1, 2, 3...)

        Returns:
            Delay em milissegundos, limitado por max_delay_ms
        """
        if attempt <= 0:
            return 0

        # Backoff exponencial: initial_delay * (backoff_factor ^ (attempt - 1))
        delay_ms = self.initial_delay_ms * (self.backoff_factor ** (attempt - 1))
        return min(int(delay_ms), self.max_delay_ms)

    def compute_delay_seconds(self, attempt: int) -> float:
        """
        Calcula delay em segundos para uma tentativa.

        Args:
            attempt: Número da tentativa (1, 2, 3...)

        Returns:
            Delay em segundos (float)
        """
        return self.compute_delay_ms(attempt) / 1000.0
