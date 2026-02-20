"""
Adaptador para o provedor Yahoo Finance usando yfinance.

Implementa busca de dados OHLCV com retry, logging estruturado
e tratamento de erros padronizado.
"""


import logging
import re
import time
import types
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.errors import FetchError, NetworkError, ValidationError

# Configuração de logging estruturado
logger = logging.getLogger(__name__)

# Tentar carregar yfinance no nível de módulo; em caso de falha, expor um wrapper/stub
try:
    import yfinance as yf  # type: ignore

    # Wrapper compatível com a API esperada pelo código legado (web.DataReader)
    def _datareader_wrapper(ticker, data_source=None, start=None, end=None, **kwargs):
        # Ignora o parâmetro `data_source` (compatibilidade com pandas_datareader API)
        # e usa `yfinance` internamente via `yf.download`
        return yf.download(ticker, start=start, end=end, progress=False)

    web = types.SimpleNamespace(DataReader=_datareader_wrapper, __is_wrapper__=True)

except (ImportError, ModuleNotFoundError):
    # stub para permitir patch de web.DataReader nos testes
    def _yf_missing(*args, **kwargs):
        raise FetchError(
            "Dependência 'yfinance' não disponível para YFinanceAdapter.fetch"
        )

    yf = types.SimpleNamespace(download=_yf_missing, __is_stub__=True)
    web = types.SimpleNamespace(DataReader=_yf_missing, __is_stub__=True)


class YFinanceAdapter(Adapter):
    """
    Adaptador para Yahoo Finance via yfinance.

    Busca dados históricos de preços com suporte a retry automático,
    backoff exponencial e logging estruturado de requisições.

    Attributes:
        max_retries: Número máximo de tentativas em caso de falha
        backoff_factor: Fator multiplicativo para backoff exponencial
        timeout: Timeout em segundos para requisições
    """

    def __init__(
        self, max_retries: int = 3, backoff_factor: float = 2.0, timeout: int = 30
    ):
        """
        Inicializa adaptador Yahoo Finance.

        Args:
            max_retries: Número de tentativas em caso de erro (padrão: 3)
            backoff_factor: Multiplicador para backoff entre retries (padrão: 2.0)
            timeout: Timeout em segundos (padrão: 30)
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout

    def fetch(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:  # noqa: C901
        """
        Busca dados OHLCV do Yahoo Finance para um ticker.

        Args:
            ticker: Código do ativo (ex: 'PETR4.SA' ou 'AAPL')
            start_date: Data de início no formato 'YYYY-MM-DD' ou 'MM-DD-YYYY'
            end_date: Data de fim no formato 'YYYY-MM-DD' ou 'MM-DD-YYYY'
            **kwargs: Argumentos adicionais ignorados (compatibilidade futura)

        Returns:
            pd.DataFrame com colunas ['Open', 'High', 'Low',
            'Close', 'Adj Close', 'Volume'] e índice DatetimeIndex.
            Metadados incluem 'source', 'ticker', 'fetched_at'.

        Raises:
            FetchError: Erro ao buscar dados
            NetworkError: Erro de rede
            ValidationError: Dados retornados inválidos

        Example:
            >>> adapter = YFinanceAdapter()
            >>> df = adapter.fetch(
            ...     'PETR4.SA', start_date='2024-01-01', end_date='2024-12-31'
            ... )
            >>> print(df.head())
        """
        # Normalizar ticker para formato Yahoo (adicionar .SA se necessário para B3)
        normalized_ticker = self._normalize_ticker(ticker)

        # Definir datas padrão se não fornecidas
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            # Padrão: último ano
            start = datetime.now() - timedelta(days=365)
            start_date = start.strftime("%Y-%m-%d")

        # Normalizar formato de datas para YYYY-MM-DD (valida formatos)
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)

        # Logging estruturado da requisição
        log_context = {
            "ticker": normalized_ticker,
            "provider": "yahoo",
            "start_date": start_date,
            "end_date": end_date,
            "max_retries": self.max_retries,
        }

        logger.info("Iniciando fetch de dados", extra=log_context)

        # Implementar retry com backoff exponencial
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                log_context["attempt"] = attempt
                log_msg = f"Tentativa {attempt} de {self.max_retries}"
                logger.debug(log_msg, extra=log_context)

                # Buscar dados usando web.DataReader (wrapper para yfinance)

                df = web.DataReader(
                    normalized_ticker,
                    data_source="yahoo",
                    start=start_date,
                    end=end_date,
                )

                # Validar estrutura do DataFrame
                self._validate_dataframe(df, normalized_ticker)

                # Adicionar metadados
                df.attrs["source"] = "yahoo"
                df.attrs["ticker"] = normalized_ticker
                df.attrs["fetched_at"] = datetime.now(timezone.utc).isoformat() + "Z"
                df.attrs["adapter"] = "YFinanceAdapter"

                log_context["status"] = "success"
                log_context["rows_fetched"] = len(df)
                log_msg = f"Dados obtidos com sucesso: {len(df)} linhas"
                logger.info(log_msg, extra=log_context)

                return df

            except (ConnectionError, TimeoutError) as e:
                last_exception = e
                log_context["status"] = "network_error"
                log_context["error_message"] = str(e)
                logger.warning(
                    f"Erro de rede na tentativa {attempt}", extra=log_context
                )

                if attempt < self.max_retries:
                    wait_time = self.backoff_factor**attempt
                    logger.debug(
                        f"Aguardando {wait_time}s antes de retry", extra=log_context
                    )
                    time.sleep(wait_time)
                else:
                    raise NetworkError(
                        "Falha de rede ao buscar "
                        f"{normalized_ticker} após {self.max_retries} tentativas",
                        original_exception=e,
                    ) from e

            except ValidationError:
                # Erros de validação não são transitórios — repropagar imediatamente
                raise

            except Exception as e:
                last_exception = e
                log_context["status"] = "fetch_error"
                log_context["error_message"] = str(e)
                log_context["error_type"] = type(e).__name__
                log_msg = f"Erro ao buscar dados na tentativa {attempt}"
                logger.error(log_msg, extra=log_context)

                if attempt < self.max_retries:
                    wait_time = self.backoff_factor**attempt
                    time.sleep(wait_time)
                else:
                    raise FetchError(
                        f"Erro ao buscar dados de {normalized_ticker}: {str(e)}",
                        original_exception=e,
                    ) from e

        # Fallback caso todas as tentativas falhem
        raise FetchError(
            (
                f"Falha ao buscar dados de {normalized_ticker} "
                f"após {self.max_retries} tentativas"
            ),
            original_exception=last_exception,
        )

    def _normalize_ticker(self, ticker: str) -> str:
        """
        Normaliza ticker para formato aceito pelo Yahoo Finance.

        Para ativos da B3, adiciona sufixo '.SA' se não presente.

        Args:
            ticker: Código do ativo

        Returns:
            Ticker normalizado
        """
        ticker = ticker.strip().upper()

        # Se já contém um sufixo (ex.: .SA, .NS) ou contém ponto, respeitar
        if "." in ticker:
            return ticker

        # Match básico para tickers alfanuméricos que terminam em dígito (B3)
        if (
            re.match(r"^[A-Z0-9]+$", ticker)
            and ticker[-1].isdigit()
            and not ticker.endswith(".SA")
        ):
            return f"{ticker}.SA"

        return ticker

    def _normalize_date(self, date_str: str) -> str:
        """
        Normaliza formato de data para YYYY-MM-DD.

        Aceita formatos: 'YYYY-MM-DD' ou 'MM-DD-YYYY'

        Args:
            date_str: String de data

        Returns:
            Data no formato 'YYYY-MM-DD'
        """
        date_str = date_str.strip()

        # Tentar YYYY-MM-DD
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            pass

        # Tentar MM-DD-YYYY
        try:
            dt = datetime.strptime(date_str, "%m-%d-%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

        # Se não casou com os formatos esperados, levantar ValidationError
        raise ValidationError(f"Formato de data inválido: {date_str}")

    def _validate_dataframe(self, df: pd.DataFrame, ticker: str) -> None:
        """
        Valida estrutura do DataFrame retornado.

        Args:
            df: DataFrame a validar
            ticker: Ticker para mensagem de erro

        Raises:
            ValidationError: Se DataFrame não possui estrutura esperada
        """
        required_columns = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

        if df.empty:
            raise ValidationError(
                f"DataFrame vazio retornado para {ticker}. "
                "Verifique se o ticker é válido e se há dados para o período."
            )

        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            raise ValidationError(
                f"Colunas obrigatórias ausentes para {ticker}: {missing_columns}"
            )

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValidationError(
                f"Índice do DataFrame não é DatetimeIndex para {ticker}"
            )

    def get_metadata(self) -> Dict[str, str]:
        """
        Retorna metadados do adaptador.

        Returns:
            Dict com informações do provedor e versões
        """
        base_metadata = super().get_metadata()

        # Detectar disponibilidade da biblioteca yfinance
        library = "yfinance"
        if hasattr(yf, "__is_stub__") and yf.__is_stub__:
            version = "unknown"
            library_available = "no"
        else:
            version = getattr(yf, "__version__", "unknown")
            library_available = "yes"

        base_metadata.update(
            {
                "provider": "yahoo",
                "library": library,
                "library_version": version,
                "library_available": library_available,
                "max_retries": str(self.max_retries),
                "backoff_factor": str(self.backoff_factor),
            }
        )
        return base_metadata
