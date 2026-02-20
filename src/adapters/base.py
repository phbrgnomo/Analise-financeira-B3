"""
Interface base para adaptadores de provedores de dados financeiros.

Define o contrato público que todos os adaptadores devem implementar.
"""

import contextlib
import json
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
    def _fetch_with_retries(
        self,
        ticker: str,
        start: str,
        end: str,
        log_context: Optional[dict] = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        timeout: Optional[float] = None,
        required_columns: Optional[List[str]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Loop de retry/backoff que chama `_fetch_once` e aplica validações genéricas.
        Mapeia exceções para `NetworkError` / `FetchError`.
        """
        last_exception = None
        if log_context is None:
            log_context = {}
        for attempt in range(1, max_retries + 1):
            try:
                log_context["attempt"] = attempt
                log_msg = f"Tentativa {attempt} de {max_retries}"
                logger.debug(log_msg, extra=log_context)

                # Passa explicitamente `timeout` para _fetch_once para que
                # provedores concretos possam aplicar timeouts nativamente.
                df = self._fetch_once(ticker, start, end, timeout=timeout, **kwargs)

                # Validar estrutura do DataFrame (padrão ou custom)
                self._validate_dataframe(df, ticker, required_columns=required_columns)

                log_context["status"] = "success"
                log_context["rows_fetched"] = len(df)
                log_msg = f"Dados obtidos com sucesso: {len(df)} linhas"
                logger.info(log_msg, extra=log_context)

                return df

            except ValidationError:
                # Propaga sem retry
                raise

            except Exception as e:
                last_exception = e

                if self._is_network_error(e):
                    log_context["status"] = "network_error"
                    log_context["error_message"] = str(e)
                    logger.warning(
                        f"Erro de rede na tentativa {attempt}", extra=log_context
                    )

                    if attempt >= max_retries:
                        raise NetworkError(
                            (
                                "Falha de rede ao buscar "
                                f"{ticker} após {max_retries} tentativas"
                            ),
                            original_exception=e,
                        ) from e

                    wait_time = self._compute_backoff(attempt, backoff_factor)
                    logger.debug(
                        f"Aguardando {wait_time}s antes de retry", extra=log_context
                    )
                    time.sleep(wait_time)
                    continue

                # Outros erros: tratar como fetch error e fazer retry até esgotar
                log_context["status"] = "fetch_error"
                log_context["error_message"] = str(e)
                log_context["error_type"] = type(e).__name__
                logger.error(
                    f"Erro ao buscar dados na tentativa {attempt}", extra=log_context
                )

                if attempt >= max_retries:
                    raise FetchError(
                        f"Erro ao buscar dados de {ticker}: {str(e)}",
                        original_exception=e,
                    ) from e

                wait_time = self._compute_backoff(attempt, backoff_factor)
                time.sleep(wait_time)

        # Fallback caso todas as tentativas falhem
        raise FetchError(
            (
                f"Falha ao buscar dados de {ticker} "
                f"após {max_retries} tentativas"
            ),
            original_exception=last_exception,
        )

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
