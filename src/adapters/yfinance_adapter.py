"""
Adaptador para o provedor Yahoo Finance usando pandas_datareader.

Implementa busca de dados OHLCV com retry, logging estruturado
e tratamento de erros padronizado.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import types

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.errors import FetchError, NetworkError, ValidationError

# Configuração de logging estruturado
logger = logging.getLogger(__name__)

# Tentar carregar pandas_datareader no nível de módulo; em caso de falha, expor um stub
try:
    from pandas_datareader import data as web  # type: ignore
except Exception:
    # stub para permitir que testes façam patch('src.adapters.yfinance_adapter.web.DataReader')
    def _pdreader_missing(*args, **kwargs):
        raise FetchError("Dependência 'pandas_datareader' não disponível para YFinanceAdapter.fetch")

    web = types.SimpleNamespace(DataReader=_pdreader_missing, __is_stub__=True)


class YFinanceAdapter(Adapter):
    """
    Adaptador para Yahoo Finance via pandas_datareader.

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
    ) -> pd.DataFrame:
        """
        Busca dados OHLCV do Yahoo Finance para um ticker.

        Args:
            ticker: Código do ativo (ex: 'PETR4.SA' ou 'AAPL')
            start_date: Data de início no formato 'YYYY-MM-DD' ou 'MM-DD-YYYY'
            end_date: Data de fim no formato 'YYYY-MM-DD' ou 'MM-DD-YYYY'
            **kwargs: Argumentos adicionais ignorados (compatibilidade futura)

        Returns:
            pd.DataFrame com colunas ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
            e índice DatetimeIndex. Metadados incluem 'source', 'ticker', 'fetched_at'.

        Raises:
            FetchError: Erro ao buscar dados
            NetworkError: Erro de rede
            ValidationError: Dados retornados inválidos

        Example:
            >>> adapter = YFinanceAdapter()
            >>> df = adapter.fetch('PETR4.SA', start_date='2024-01-01', end_date='2024-12-31')
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

        # Normalizar formato de datas para YYYY-MM-DD
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

        logger.info(f"Iniciando fetch de dados", extra=log_context)

        # Implementar retry com backoff exponencial
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                log_context["attempt"] = attempt
                logger.debug(f"Tentativa {attempt} de {self.max_retries}", extra=log_context)

                # Buscar dados do Yahoo Finance (usa `web` module-level se mockado em testes, caso contrário carrega pandas_datareader)
                global web
                if web is None:
                    try:
                        from pandas_datareader import data as web_module  # import local
                        web = web_module
                    except Exception as e:
                        raise FetchError(
                            "Dependência 'pandas_datareader' não disponível para YFinanceAdapter.fetch",
                            original_exception=e,
                        )
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
                df.attrs["fetched_at"] = datetime.utcnow().isoformat() + "Z"
                df.attrs["adapter"] = "YFinanceAdapter"

                log_context["status"] = "success"
                log_context["rows_fetched"] = len(df)
                logger.info(
                    f"Dados obtidos com sucesso: {len(df)} linhas", extra=log_context
                )

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
                        f"Falha de rede ao buscar {normalized_ticker} após {self.max_retries} tentativas",
                        original_exception=e,
                    )

            except Exception as e:
                # Erros de validação não são transitórios — repropagar imediatamente
                if isinstance(e, ValidationError):
                    raise

                last_exception = e
                log_context["status"] = "fetch_error"
                log_context["error_message"] = str(e)
                log_context["error_type"] = type(e).__name__
                logger.error(f"Erro ao buscar dados na tentativa {attempt}", extra=log_context)

                if attempt < self.max_retries:
                    wait_time = self.backoff_factor**attempt
                    time.sleep(wait_time)
                else:
                    raise FetchError(
                        f"Erro ao buscar dados de {normalized_ticker}: {str(e)}",
                        original_exception=e,
                    )

        # Fallback caso todas as tentativas falhem
        raise FetchError(
            f"Falha ao buscar dados de {normalized_ticker} após {self.max_retries} tentativas",
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

        # Identificar se é ativo B3 (termina com número)
        # Ex: PETR4, VALE3, ITUB3 -> adicionar .SA
        if ticker and ticker[-1].isdigit() and not ticker.endswith(".SA"):
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

        # Detectar formato MM-DD-YYYY (usado no código legado)
        if "-" in date_str:
            parts = date_str.split("-")
            if len(parts) == 3:
                # Se primeiro campo tem 4 dígitos, já está em YYYY-MM-DD
                if len(parts[0]) == 4:
                    return date_str
                # Caso contrário, converter MM-DD-YYYY -> YYYY-MM-DD
                elif len(parts[2]) == 4:
                    return f"{parts[2]}-{parts[0]}-{parts[1]}"

        return date_str

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
        base_metadata.update(
            {
                "provider": "yahoo",
                "library": "pandas_datareader",
                "max_retries": str(self.max_retries),
                "backoff_factor": str(self.backoff_factor),
            }
        )
        return base_metadata
