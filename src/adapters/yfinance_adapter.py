"""
Adaptador para o provedor Yahoo Finance usando yfinance.

Implementa busca de dados OHLCV com retry, logging estruturado
e tratamento de erros padronizado.
"""



import logging
import re
import types
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pandas as pd

from src.adapters.base import Adapter
from src.adapters.errors import FetchError

# Configuração de logging estruturado
logger = logging.getLogger(__name__)

# Tentar carregar yfinance no nível de módulo; em caso de falha, expor um wrapper/stub
try:
    import yfinance as yf  # type: ignore

    # Wrapper compatível com a API esperada pelo código legado (web.DataReader)
    def _datareader_wrapper(ticker, data_source=None, start=None, end=None, **kwargs):
        # Ignora o parâmetro `data_source` (compatibilidade com pandas_datareader API)
        # e usa `yfinance` internamente via `yf.download`
        return yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            **kwargs,
        )

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
        self,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
        timeout: int | None = None,
        retry_config=None,
    ):
        """
        Inicializa adaptador Yahoo Finance.

        Args:
            max_retries: Número de tentativas (usa RetryConfig por padrão)
            backoff_factor: Fator de backoff (usa RetryConfig por padrão)
            timeout: Timeout em segundos (usa RetryConfig por padrão)
            retry_config: Optional RetryConfig para configurar políticas
        """
        # Inicializa Adapter base para carregar RetryConfig e métricas
        super().__init__(retry_config=retry_config)

        # Priorizar parâmetros explícitos ou herdar da retry_config
        self.max_retries = 3 if max_retries is None else max_retries
        self.backoff_factor = 2.0 if backoff_factor is None else backoff_factor
        self.timeout = 30 if timeout is None else timeout

        if hasattr(self, "retry_config") and self.retry_config:
            if max_retries is None:
                self.max_retries = self.retry_config.max_attempts
            if backoff_factor is None:
                self.backoff_factor = self.retry_config.backoff_factor
            if timeout is None:
                self.timeout = self.retry_config.timeout_seconds

    def fetch(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:    # noqa: C901
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

        # Definir datas padrão se não fornecidas usando uma única referência de tempo
        now = datetime.now()
        if end_date is None:
            end_date = now.strftime("%Y-%m-%d")
        if start_date is None:
            # Padrão: último ano
            start = now - timedelta(days=365)
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

        # Delegar obtenção com retry para helper implementado no Adapter base
        df = super()._fetch_with_retries(
            normalized_ticker,
            start_date,
            end_date,
            log_context=log_context,
            max_retries=self.max_retries,
            backoff_factor=self.backoff_factor,
            timeout=self.timeout,
            **kwargs,
        )

        # Adicionar metadados
        df.attrs["source"] = "yahoo"
        df.attrs["ticker"] = normalized_ticker
        fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        df.attrs["fetched_at"] = fetched_at
        df.attrs["adapter"] = "YFinanceAdapter"

        return df

    def _fetch_with_retries(
        self,
        ticker: str,
        start: str,
        end: str,
        log_context: Optional[dict] = None,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        timeout: Optional[float] = None,
        required_columns: Optional[list] = None,
        idempotent: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Tenta obter os dados remotos com retry e backoff exponencial.

        Este método encapsula a lógica de retry e de captura de exceções
        relacionadas a rede/erros de API.
        """
        # Backwards-compatible wrapper: delega para a implementação no Adapter base.
        return super()._fetch_with_retries(
            ticker,
            start,
            end,
            log_context=log_context,
            max_retries=(
                self.max_retries if max_retries is None else max_retries
            ),
            backoff_factor=(
                self.backoff_factor
                if backoff_factor is None
                else backoff_factor
            ),
            timeout=(self.timeout if timeout is None else timeout),
            required_columns=required_columns,
            idempotent=idempotent,
            **kwargs,
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
        # Match básico para tickers alfanuméricos que terminam em dígito (B3)
        if (
            re.match(r"^[A-Z0-9]+$", ticker)
            and ticker[-1].isdigit()
            and not ticker.endswith(".SA")
        ):
            return f"{ticker}.SA"

        return ticker

    # _normalize_date and _validate_dataframe are inherited from Adapter base

    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        """
        Implementação única de fetch para o provedor Yahoo (usado pelo base retry).
        """
        return web.DataReader(
            ticker, data_source="yahoo", start=start, end=end, **kwargs
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
        # Use getattr to avoid accessing an attribute that may not exist
        # on the real `yfinance` module (silences static analysis warnings).
        if getattr(yf, "__is_stub__", False):
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
