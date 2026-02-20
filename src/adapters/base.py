"""
Interface base para adaptadores de provedores de dados financeiros.

Define o contrato público que todos os adaptadores devem implementar.
"""

import contextlib
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from src.adapters.errors import FetchError, NetworkError, ValidationError
from src.adapters.retry_config import RetryConfig
from src.adapters.retry_metrics import get_global_metrics

logger = logging.getLogger(__name__)


class Adapter(ABC):
    """
    Interface abstrata para adaptadores de provedores de dados financeiros.

    Todos os adaptadores concretos devem herdar desta classe e implementar
    o método fetch() para buscar dados de um ticker específico.

    O adaptador é responsável apenas por buscar dados brutos do provedor,
    sem realizar persistência ou transformações complexas.
    """

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """
        Inicializa adaptador com configuração de retry.

        Args:
            retry_config: Configuração de retry. Se None, carrega do ambiente.
        """
        self.retry_config = retry_config or RetryConfig.from_env()
        self._metrics = get_global_metrics()

    @abstractmethod
    def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
        """
        Busca dados brutos para um ticker do provedor.

        Args:
            ticker: Código do ativo (ex: 'PETR4' para B3, 'AAPL' para NYSE)
            **kwargs: Parâmetros adicionais específicos do provedor
                      (ex: start_date, end_date, period)

        Returns:
            pd.DataFrame: DataFrame com dados OHLCV do provedor.
                         Deve conter pelo menos as colunas:
                         ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
                         O DataFrame deve ter um índice DatetimeIndex.

        Raises:
            AdapterError: Erro genérico do adaptador
            FetchError: Falha ao buscar dados do provedor
            NetworkError: Erro de conectividade
            ValidationError: Dados retornados não possuem formato esperado
            RateLimitError: Limite de requisições atingido

        Notes:
            - Adaptador deve adicionar metadado 'source' ao DataFrame.attrs
            - Timestamps devem ser normalizados para UTC quando possível
            - Não realiza persistência; apenas retorna dados brutos
        """
        raise NotImplementedError()

    @abstractmethod
    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        """
        Implementação concreta deve buscar os dados uma única vez sem retry.

        Retorna o `pd.DataFrame` bruto do provedor.
        """
        raise NotImplementedError()

    def _normalize_date(self, date_str: str) -> str:
        """
        Normaliza formato de data para YYYY-MM-DD.

        Aceita formatos: 'YYYY-MM-DD' ou 'MM-DD-YYYY'
        """
        date_str = date_str.strip()

        # Tentar YYYY-MM-DD
        with contextlib.suppress(ValueError):
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        # Tentar MM-DD-YYYY
        with contextlib.suppress(ValueError):
            dt = datetime.strptime(date_str, "%m-%d-%Y")
            return dt.strftime("%Y-%m-%d")
        # Se não casou com os formatos esperados, levantar ValidationError
        raise ValidationError(f"Formato de data inválido: {date_str}")

    def _validate_dataframe(
        self,
        df: pd.DataFrame,
        ticker: str,
        required_columns: Optional[List[str]] = None,
    ) -> None:
        """
        Valida estrutura do DataFrame retornado.

        Levanta `ValidationError` com mensagens compatíveis com os testes existentes.
        """
        if required_columns is None:
            required_columns = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

        if df.empty:
            raise ValidationError(
                f"DataFrame vazio retornado para {ticker}. "
                "Verifique se o ticker é válido e se há dados para o período."
            )

        if missing_columns := set(required_columns) - set(df.columns):
            raise ValidationError(
                f"Colunas obrigatórias ausentes para {ticker}: {missing_columns}"
            )

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValidationError(
                f"Índice do DataFrame não é DatetimeIndex para {ticker}"
            )

    def _is_network_error(self, e: Exception) -> bool:
        """
        Heurística para identificar erros de rede que justificam retry.

        Centraliza a classificação por nome/tipo/módulo para manter a
        lógica do loop de retry mais legível.
        """
        err_name = type(e).__name__
        is_network = err_name in ("ConnectionError", "TimeoutError")

        # Exceções vindas do namespace 'requests' também devem ser tratadas
        # como erros de rede.
        module_name = getattr(e, "__module__", "")
        if hasattr(e, "__class__") and module_name.startswith("requests"):
            is_network = True

        return is_network

    def _compute_backoff(self, attempt: int, backoff_factor: float) -> float:
        """Calcula o tempo de espera (backoff exponencial) para uma tentativa."""
        try:
            return backoff_factor ** attempt
        except Exception:
            # fallback seguro
            return float(backoff_factor) * attempt

    def _extract_status_code(self, e: Exception):
        """Extrai código HTTP se presente na exceção."""
        if hasattr(e, "response"):
            return getattr(e.response, "status_code", None)
        if hasattr(e, "status_code"):
            return getattr(e, "status_code", None)
        return None

    def _is_retryable_exception(self, e: Exception, status_code) -> bool:
        """Decide se uma exceção é elegível para retry."""
        if status_code is not None and hasattr(self, "retry_config"):
            if status_code in self.retry_config.retry_on_status_codes:
                return True
        return self._is_network_error(e)

    def _compute_wait(self, attempt: int, backoff_factor: float) -> tuple[float, int]:
        """Retorna (wait_seconds, delay_ms) para a tentativa atual."""
        if hasattr(self, "retry_config"):
            wait = self.retry_config.compute_delay_seconds(attempt)
            delay_ms = self.retry_config.compute_delay_ms(attempt)
        else:
            wait = self._compute_backoff(attempt, backoff_factor)
            delay_ms = int(wait * 1000)
        return wait, delay_ms

    def _fetch_with_retries(  # noqa: C901
        self,
        ticker: str,
        start: str,
        end: str,
        log_context: Optional[dict] = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        timeout: Optional[float] = None,
        required_columns: Optional[List[str]] = None,
        idempotent: bool = True,
        **kwargs,
    ) -> pd.DataFrame:  # noqa: C901
        """
        Loop de retry/backoff que chama `_fetch_once` e aplica validações genéricas.
        Mapeia exceções para `NetworkError` / `FetchError`.

        Novidades:
        - Registra métricas por tentativa (RetryMetrics)
        - Registra logs estruturados com `attempt`, `next_delay_ms` e `error_message`
        - Respeita idempotência: se idempotent=False, retries são desabilitados
        - Usa `RetryConfig` se disponível para calcular delays
        """
        last_exception = None
        if log_context is None:
            log_context = {}

        metrics = getattr(self, "_metrics", get_global_metrics())

        effective_max_retries = max_retries
        if not idempotent and max_retries > 1:
            logger.warning(
                "Operação não-idempotente; desabilitando retries",
                extra={**log_context, "idempotent": False},
            )
            effective_max_retries = 1

        for attempt in range(1, effective_max_retries + 1):
            metrics.record_attempt()
            try:
                log_context["attempt"] = attempt
                msg = f"Tentativa {attempt} de {effective_max_retries}"
                logger.debug(msg, extra=log_context)

                df = self._fetch_once(ticker, start, end, timeout=timeout, **kwargs)

                self._validate_dataframe(df, ticker, required_columns=required_columns)

                log_context["status"] = "success"
                log_context["rows_fetched"] = len(df)
                msg = f"Dados obtidos com sucesso: {len(df)} linhas"
                logger.info(msg, extra=log_context)

                if attempt == 1:
                    metrics.record_first_attempt_success()
                else:
                    metrics.record_success_after_retry()

                return df

            except ValidationError:
                raise

            except Exception as e:
                last_exception = e

                status_code = self._extract_status_code(e)
                if self._is_retryable_exception(e, status_code):
                    log_context["status"] = "retryable_error"
                    log_context["error_message"] = str(e)
                    if status_code is not None:
                        log_context["http_status"] = status_code
                    msg = f"Erro retryable na tentativa {attempt}"
                    logger.warning(msg, extra=log_context)

                    if attempt >= effective_max_retries:
                        metrics.record_permanent_failure()
                        msg = (
                            f"Falha de rede ao buscar {ticker} "
                            f"após {effective_max_retries} tentativas"
                        )
                        raise NetworkError(msg, original_exception=e) from e

                    wait_time, delay_ms = self._compute_wait(attempt, backoff_factor)
                    metrics.record_retry()
                    log_context["next_delay_ms"] = delay_ms
                    msg = f"Aguardando {wait_time}s antes de retry"
                    logger.debug(msg, extra=log_context)
                    time.sleep(wait_time)
                    continue

                # Outros erros: tratar como fetch error
                log_context["status"] = "fetch_error"
                log_context["error_message"] = str(e)
                log_context["error_type"] = type(e).__name__
                msg = f"Erro ao buscar dados na tentativa {attempt}"
                logger.error(msg, extra=log_context)

                if attempt >= effective_max_retries:
                    metrics.record_permanent_failure()
                    raise FetchError(
                        f"Erro ao buscar dados de {ticker}: {str(e)}",
                        original_exception=e,
                    ) from e

                wait_time, delay_ms = self._compute_wait(attempt, backoff_factor)
                metrics.record_retry()
                log_context["next_delay_ms"] = delay_ms
                time.sleep(wait_time)

        msg = (
            f"Falha ao buscar dados de {ticker} "
            f"após {effective_max_retries} tentativas"
        )
        raise FetchError(msg, original_exception=last_exception)

    def get_metadata(self) -> Dict[str, str]:
        """
        Retorna metadados do adaptador.

        Returns:
            Dict com informações do provedor:
            - 'provider': Nome do provedor (ex: 'yahoo', 'alphavantage')
            - 'version': Versão da biblioteca usada
            - 'adapter_version': Versão do adaptador
        """
        return {
            "provider": self.__class__.__name__.replace("Adapter", "").lower(),
            "adapter_version": "1.0.0",
        }
