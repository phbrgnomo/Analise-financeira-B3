"""
Testes unitários para adaptadores de provedores de dados.

Testa interface Adapter, erros customizados e implementação YFinanceAdapter
usando mocks para garantir determinismo e isolamento de rede.
"""

import types
from unittest.mock import patch

import pandas as pd
import pytest

from src.adapters.base import Adapter
from src.adapters.errors import (
    AdapterError,
    FetchError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from src.adapters.yfinance_adapter import YFinanceAdapter


@pytest.fixture
def minimal_adapter():
    """Factory fixture returning a minimal Adapter instance.

    The returned object is a concrete Adapter subclass that implements only the
    bare minimum needed for unit tests: it can be instantiated and its helper
    methods (e.g. _normalize_date, _validate_dataframe) can be exercised.

    If required columns should be customized, pass `required_columns` when
    calling the factory (e.g. `minimal_adapter(required_columns=[...])`).
    """

    def _make(required_columns: list[str] | None = None):
        class TestAdapter(Adapter):
            def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
                return pd.DataFrame()

            def _fetch_once(
                self, ticker: str, start: str, end: str, **kwargs
            ) -> pd.DataFrame:
                return pd.DataFrame()

        if required_columns is not None:
            TestAdapter.REQUIRED_COLUMNS = required_columns

        return TestAdapter()

    return _make


class TestAdapterErrors:
    """Testa hierarquia de erros customizados."""

    def test_adapter_error_basic(self):
        """Testa criação de AdapterError básico."""
        error = AdapterError("Erro de teste", code="TEST_ERROR")
        assert error.message == "Erro de teste"
        assert error.code == "TEST_ERROR"
        assert error.original_exception is None
        assert str(error) == "[TEST_ERROR] Erro de teste"

    def test_adapter_error_with_original_exception(self):
        """Testa AdapterError com exceção original encadeada."""
        original = ValueError("Erro original")
        error = AdapterError(
            "Erro wrapper",
            code="WRAPPER",
            original_exception=original,
        )
        assert error.original_exception == original
        assert "caused by" in str(error)
        assert "Erro original" in str(error)

    def test_fetch_error(self):
        """Testa FetchError especializado."""
        error = FetchError("Erro ao buscar dados")
        assert error.code == "FETCH_ERROR"
        assert "Erro ao buscar dados" in str(error)

    def test_network_error(self):
        """Testa NetworkError especializado."""
        error = NetworkError("Timeout na requisição")
        assert error.code == "NETWORK_ERROR"

    def test_validation_error(self):
        """Testa ValidationError especializado."""
        error = ValidationError("Dados inválidos")
        assert error.code == "VALIDATION_ERROR"

    def test_rate_limit_error(self):
        """Testa RateLimitError especializado."""
        error = RateLimitError("Limite de requisições atingido")
        assert error.code == "RATE_LIMIT_ERROR"


class TestAdapterInterface:
    """Testa interface abstrata Adapter."""

    def test_adapter_is_abstract(self):
        """Testa que Adapter não pode ser instanciado diretamente."""
        with pytest.raises(TypeError):
            Adapter()  # type: ignore

    def test_adapter_requires_fetch_implementation(self):
        """Testa que subclasses devem implementar fetch()."""

        class IncompleteAdapter(Adapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore

    def test_adapter_get_metadata(self):
        """Testa método get_metadata() padrão."""

        class TestAdapter(Adapter):
            def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
                return pd.DataFrame()

            def _fetch_once(
                self,
                ticker: str,
                start: str,
                end: str,
                **kwargs,
            ) -> pd.DataFrame:
                # implementação mínima para satisfazer contrato abstrato
                return pd.DataFrame()

        adapter = TestAdapter()
        metadata = adapter.get_metadata()
        assert "provider" in metadata
        assert "adapter_version" in metadata
        assert metadata["provider"] == "test"


class TestYFinanceAdapter:
    """Testa implementação concreta YFinanceAdapter."""

    def test_adapter_initialization(self):
        """Testa inicialização com parâmetros padrão."""
        adapter = YFinanceAdapter()
        self._assert_adapter_config(adapter, 3, 2.0, 30)

    def test_adapter_custom_initialization(self):
        """Testa inicialização com parâmetros customizados."""
        adapter = YFinanceAdapter(max_retries=5, backoff_factor=1.5, timeout=60)
        self._assert_adapter_config(adapter, 5, 1.5, 60)

    def _assert_adapter_config(
        self,
        adapter,
        expected_retries,
        expected_backoff,
        expected_timeout,
    ):
        """Verifica configuração de retry do adapter."""
        assert adapter.max_retries == expected_retries
        assert adapter.backoff_factor == expected_backoff
        assert adapter.timeout == expected_timeout

    def test_normalize_ticker_b3(self):
        """Testa normalização de tickers B3 (adiciona .SA)."""
        adapter = self._assert_ticker_normalization(
            "PETR4", "PETR4.SA", "vale3", "VALE3.SA"
        )
        assert adapter._normalize_ticker("ITUB3") == "ITUB3.SA"

    def test_normalize_ticker_already_has_suffix(self):
        """Testa que ticker com .SA não é modificado."""
        adapter = YFinanceAdapter()
        assert adapter._normalize_ticker("PETR4.SA") == "PETR4.SA"

    def test_normalize_ticker_non_b3(self):
        """Testa que tickers sem número não recebem .SA."""
        self._assert_ticker_normalization("AAPL", "AAPL", "MSFT", "MSFT")

    def _assert_ticker_normalization(
        self,
        ticker_a,
        expected_a,
        ticker_b,
        expected_b,
    ):
        """Verifica normalização de dois tickers."""
        adapter = YFinanceAdapter()
        assert adapter._normalize_ticker(ticker_a) == expected_a
        assert adapter._normalize_ticker(ticker_b) == expected_b
        return adapter

    def test_normalize_date_yyyy_mm_dd(self):
        """Testa normalização de data YYYY-MM-DD (já normalizada)."""
        self._assert_date_normalization("2024-01-01", "2024-01-01", "2024-12-31")

    def _assert_date_normalization(
        self,
        date_input,
        expected_output,
        second_date,
    ):
        """Verifica normalização de datas no adapter."""
        adapter = YFinanceAdapter()
        assert adapter._normalize_date(date_input) == expected_output
        assert adapter._normalize_date(second_date) == "2024-12-31"

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    def test_fetch_success(self, mock_datareader):
        """Testa fetch bem-sucedido com mock de dados."""
        # Preparar DataFrame de teste
        dates = pd.date_range("2024-01-01", periods=5)
        mock_df = pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104],
                "High": [105, 106, 107, 108, 109],
                "Low": [99, 100, 101, 102, 103],
                "Close": [102, 103, 104, 105, 106],
                "Adj Close": [102, 103, 104, 105, 106],
                "Volume": [1000, 1100, 1200, 1300, 1400],
            },
            index=dates,
        )
        mock_datareader.return_value = mock_df

        adapter = YFinanceAdapter()
        result = adapter.fetch("PETR4", start_date="2024-01-01", end_date="2024-01-05")

        # Verificar chamada ao DataReader
        mock_datareader.assert_called_once_with(
            "PETR4.SA",
            data_source="yfinance",
            start="2024-01-01",
            end="2024-01-05",
            timeout=30,
        )

        # Verificar resultado
        assert len(result) == 5
        assert list(result.columns) == [
            "Open",
            "High",
            "Low",
            "Close",
            "Adj Close",
            "Volume",
        ]
        assert isinstance(result.index, pd.DatetimeIndex)

        # Verificar metadados
        assert result.attrs["source"] == "yfinance"
        assert result.attrs["ticker"] == "PETR4.SA"
        assert "fetched_at" in result.attrs
        assert result.attrs["adapter"] == "YFinanceAdapter"

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    def test_fetch_empty_dataframe_raises_validation_error(self, mock_datareader):
        """Testa que DataFrame vazio levanta ValidationError."""
        mock_datareader.return_value = pd.DataFrame()

        adapter = YFinanceAdapter()
        with pytest.raises(ValidationError) as exc_info:
            adapter.fetch("INVALID")

        assert "DataFrame vazio" in str(exc_info.value)

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    def test_fetch_missing_columns_raises_validation_error(self, mock_datareader):
        """Testa que falta de colunas obrigatórias levanta ValidationError."""
        dates = pd.date_range("2024-01-01", periods=3)
        incomplete_df = pd.DataFrame(
            {"Open": [100, 101, 102], "Close": [102, 103, 104]}, index=dates
        )
        mock_datareader.return_value = incomplete_df

        adapter = YFinanceAdapter()
        with pytest.raises(ValidationError) as exc_info:
            adapter.fetch("PETR4")

        assert "Colunas obrigatórias ausentes" in str(exc_info.value)
        assert "High" in str(exc_info.value)

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    @patch("src.adapters.base.time.sleep")
    def test_fetch_network_error_with_retry(self, mock_sleep, mock_datareader):
        """Testa retry automático em caso de erro de rede."""
        # Primeira tentativa: erro de rede
        # Segunda tentativa: sucesso
        dates = pd.date_range("2024-01-01", periods=2)
        success_df = pd.DataFrame(
            {
                "Open": [100, 101],
                "High": [105, 106],
                "Low": [99, 100],
                "Close": [102, 103],
                "Adj Close": [102, 103],
                "Volume": [1000, 1100],
            },
            index=dates,
        )

        mock_datareader.side_effect = [ConnectionError("Network timeout"), success_df]

        adapter = YFinanceAdapter(max_retries=3, backoff_factor=2.0)
        result = adapter.fetch("PETR4")

        # Verificar que houve retry
        assert mock_datareader.call_count == 2
        assert mock_sleep.call_count == 1  # Esperou antes do retry
        assert len(result) == 2

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    @patch("src.adapters.base.time.sleep")
    def test_fetch_max_retries_exceeded_raises_network_error(
        self, mock_sleep, mock_datareader
    ):
        """Testa que NetworkError é levantado após esgotar retries."""
        mock_datareader.side_effect = ConnectionError("Network timeout")

        adapter = YFinanceAdapter(max_retries=3)
        with pytest.raises(NetworkError) as exc_info:
            adapter.fetch("PETR4")

        assert "Falha de rede" in str(exc_info.value)
        assert "3 tentativas" in str(exc_info.value)
        assert mock_datareader.call_count == 3

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    @patch("src.adapters.base.time.sleep")
    def test_fetch_generic_error_with_retry(self, mock_sleep, mock_datareader):
        """Testa retry em caso de erro genérico."""
        dates = pd.date_range("2024-01-01", periods=2)
        success_df = pd.DataFrame(
            {
                "Open": [100, 101],
                "High": [105, 106],
                "Low": [99, 100],
                "Close": [102, 103],
                "Adj Close": [102, 103],
                "Volume": [1000, 1100],
            },
            index=dates,
        )

        mock_datareader.side_effect = [ValueError("API Error"), success_df]

        adapter = YFinanceAdapter(max_retries=3)
        result = adapter.fetch("PETR4")

        assert mock_datareader.call_count == 2
        assert len(result) == 2

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    @patch("src.adapters.base.time.sleep")
    def test_fetch_all_retries_fail_raises_fetch_error(
        self, mock_sleep, mock_datareader
    ):
        """Testa que FetchError é levantado após esgotar retries em erro genérico."""
        mock_datareader.side_effect = ValueError("API Error")

        adapter = YFinanceAdapter(max_retries=2)
        with pytest.raises(FetchError) as exc_info:
            adapter.fetch("PETR4")

        assert "Erro ao buscar dados" in str(exc_info.value)
        assert mock_datareader.call_count == 2

    @patch("src.adapters.yfinance_adapter.web.DataReader")
    def test_fetch_uses_default_dates(self, mock_datareader):
        """Testa que datas padrão são usadas quando não fornecidas."""
        dates = pd.date_range("2024-01-01", periods=2)
        mock_df = pd.DataFrame(
            {
                "Open": [100, 101],
                "High": [105, 106],
                "Low": [99, 100],
                "Close": [102, 103],
                "Adj Close": [102, 103],
                "Volume": [1000, 1100],
            },
            index=dates,
        )
        mock_datareader.return_value = mock_df

        adapter = YFinanceAdapter()
        adapter.fetch("PETR4")

        # Verificar que DataReader foi chamado com datas
        call_args = mock_datareader.call_args
        assert call_args[1]["start"] is not None
        assert call_args[1]["end"] is not None

    def test_get_metadata(self):
        """Testa metadados retornados pelo adaptador."""
        adapter = YFinanceAdapter(max_retries=5)
        metadata = adapter.get_metadata()

        assert metadata["provider"] == "yfinance"
        assert metadata["library"] == "yfinance"
        assert metadata["max_retries"] == "5"
        assert "adapter_version" in metadata
        # Verifica disponibilidade e versão da biblioteca yfinance
        assert "library_available" in metadata
        assert "library_version" in metadata
        # evitar condicionais em testes (Sourcery): garantir que não estamos
        # no caso inconsistente onde a biblioteca é reportada como disponível
        # mas a versão é 'unknown'
        assert not (
            metadata["library_available"] == "yes"
            and metadata["library_version"] == "unknown"
        )

    def test_get_metadata_when_yfinance_missing(self, monkeypatch):
        """Simula yfinance ausente e verifica metadados resultantes."""
        # Substitui o objeto `yf` do módulo por um stub indicando ausência
        monkeypatch.setattr(
            "src.adapters.yfinance_adapter.yf",
            types.SimpleNamespace(__is_stub__=True),
            raising=False,
        )

        adapter = YFinanceAdapter()
        metadata = adapter.get_metadata()

        assert metadata["library_available"] == "no"
        assert metadata["library_version"] == "unknown"


class TestAdapterBaseHelpers:
    """Testes para helpers centralizados em `Adapter` (normalize/validate)."""

    def test_adapter_normalize_date_valid_formats(self, minimal_adapter):
        adapter = minimal_adapter()

        normalized_iso = adapter._normalize_date("2023-02-15")
        assert normalized_iso == "2023-02-15"

        normalized_us = adapter._normalize_date("02-15-2023")
        assert normalized_us == "2023-02-15"

    def test_adapter_normalize_date_invalid_format_raises_validation_error(
        self, minimal_adapter
    ):
        adapter = minimal_adapter()

        with pytest.raises(ValidationError) as excinfo:
            adapter._normalize_date("15/02/2023")

        assert "Formato de data inválido" in str(excinfo.value)

    def test_adapter_validate_dataframe_empty_raises_validation_error(
        self, minimal_adapter
    ):
        adapter = minimal_adapter()
        df = pd.DataFrame()

        with pytest.raises(ValidationError, match="DataFrame vazio"):
            adapter._validate_dataframe(df, "TICKER")

    def test_validate_dataframe_missing_required_columns_mentions_them(
        self, minimal_adapter
    ):
        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Adj Close",
            "Volume",
        ]
        adapter = minimal_adapter(required_columns=required_columns)

        index = pd.date_range("2023-01-01", periods=3, freq="D")
        # criar um DataFrame não-vazio mas sem as colunas requeridas
        df = pd.DataFrame({"foo": [1, 2, 3]}, index=index)

        with pytest.raises(ValidationError) as excinfo:
            adapter._validate_dataframe(df, "TICKER")

        msg = str(excinfo.value)
        assert all(col in msg for col in required_columns)

    def test_validate_dataframe_accepts_lowercase_columns(self, minimal_adapter):
        """Validation should be case‑insensitive for column names."""

        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        adapter = minimal_adapter(required_columns=required_columns)
        index = pd.date_range("2023-01-01", periods=2, freq="D")
        # use lowercase column headers to simulate provider variation
        df = pd.DataFrame(
            {
                "open": [1, 2],
                "high": [1, 2],
                "low": [1, 2],
                "close": [1, 2],
                "volume": [100, 200],
            },
            index=index,
        )
        # should not raise
        adapter._validate_dataframe(df, "TICKER")

    def test_validate_dataframe_flatten_multiindex_columns(self, minimal_adapter):
        """Adapters should cope with MultiIndex column names (yfinance)."""

        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        adapter = minimal_adapter(required_columns=required_columns)

        # create MultiIndex that mimics yfinance returned frame
        arrays = [
            ["Close", "High", "Low", "Open", "Volume"],
            ["TICK"] * 5,
        ]
        cols = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        df = pd.DataFrame(
            [[1, 2, 3, 4, 5]],
            columns=cols,
            index=pd.date_range("2023-01-01", periods=1),
        )

        # this should not raise even though columns are tuples
        adapter._validate_dataframe(df, "TICK")

    def test_validate_dataframe_non_datetime_index(self, minimal_adapter):
        """Adapter._validate_dataframe should reject non-DatetimeIndex input.

        This uses a minimal Adapter instance and calls `adapter._validate_dataframe(
        "TICKER")` with a DataFrame that has required columns but an integer
        index, which should raise ValidationError.
        """

        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Adj Close",
            "Volume",
        ]
        adapter = minimal_adapter(required_columns=required_columns)

        # criar DataFrame com todas as colunas requeridas, mas índice não Datetime
        df = pd.DataFrame(
            {
                "Open": [1.0],
                "High": [1.1],
                "Low": [0.9],
                "Close": [1.0],
                "Adj Close": [1.0],
                "Volume": [100],
            },
            index=[0],
        )

        with pytest.raises(
            ValidationError, match="Índice do DataFrame não é DatetimeIndex"
        ):
            adapter._validate_dataframe(df, "TICKER")
