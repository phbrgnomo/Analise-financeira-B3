import builtins
import logging
import types
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.base import Adapter, logger


class DummyAdapter(Adapter):
    """Minimal concrete Adapter to allow instantiation for tests."""

    def fetch(self, ticker: str, **kwargs):
        """Fetch data for a given ticker.

        Parameters
        ----------
        ticker:
            Ticker symbol to fetch data for.
        **kwargs:
            Adapter-specific keyword arguments.

        Returns
        -------
        Any
            Implementation-specific fetched data.
        """

        raise NotImplementedError

    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs):
        """Perform a single fetch window for the given ticker.

        Parameters
        ----------
        ticker:
            Ticker symbol.
        start:
            Start timestamp (ISO string).
        end:
            End timestamp (ISO string).
        **kwargs:
            Adapter-specific options.

        Returns
        -------
        Any
            Implementation-specific result for the fetch window.
        """

        raise NotImplementedError


@pytest.mark.parametrize(
    "exc, ticker, provider_name, expected_reason_message",
    [
        pytest.param(
            ValueError("invalid data format"),
            "PETR4",
            "yahoo",
            "invalid data format",
            id="happy-path-value-error-simple-message",
        ),
        pytest.param(
            RuntimeError("complex error with ünicode"),
            "AAPL",
            "alphavantage",
            "complex error with ünicode",
            id="happy-path-runtime-error-unicode-message",
        ),
        pytest.param(
            Exception(""),
            "MSFT",
            "custom_provider",
            "",
            id="happy-path-empty-error-message",
        ),
    ],
)
def test_log_adapter_validation_happy_path(
    exc, ticker, provider_name, expected_reason_message
):
    """Verifica o fluxo feliz de `_log_adapter_validation`.

    Cenário: recebe uma exceção `exc`, um `ticker` e `provider_name` via
    `adapter.get_metadata`. Espera-se que a função construa um registro de
    validação e chame `log_invalid_rows` com um único `error_record` cujo
    `reason_message` corresponde à mensagem da exceção.

    Pré-condições: o módulo `src.validation` é substituído por um mock que
    expõe `log_invalid_rows` e `adapter.get_metadata` retorna um dicionário
    contendo a chave `provider`.
    """

    adapter = DummyAdapter()
    adapter.get_metadata = MagicMock(return_value={"provider": provider_name})

    log_invalid_rows_mock = MagicMock()

    # We will capture the imported module src.validation with our mock object
    mock_validation_module = types.SimpleNamespace(
        log_invalid_rows=log_invalid_rows_mock,
    )

    log_context = {"existing": "context"}

    with patch.dict(
        "sys.modules",
        {
            "src.validation": mock_validation_module,
        },
    ):
        # Act

        adapter._log_adapter_validation(exc, ticker, log_context)

    # Assert

    log_invalid_rows_mock.assert_called_once()
    call_kwargs = log_invalid_rows_mock.call_args.kwargs

    assert call_kwargs["metadata_path"] == "metadata/ingest_logs.json"
    assert call_kwargs["provider"] == provider_name
    assert call_kwargs["ticker"] == ticker
    assert call_kwargs["raw_file"] == ""
    assert call_kwargs["invalid_filepath"] == ""
    assert call_kwargs["job_id"] == ""

    error_records = call_kwargs["error_records"]
    assert isinstance(error_records, list)
    assert len(error_records) == 1
    record = error_records[0]

    assert record["row_index"] is None
    assert record["column"] is None
    assert record["reason_code"] == "ADAPTER_VALIDATION"
    assert record["reason_message"] == expected_reason_message


@pytest.mark.parametrize(
    "ticker, provider_name, error_message",
    [
        pytest.param(
            "TICKER1",
            "",
            "some error",
            id="edge-case-empty-provider-name",
        ),
        pytest.param(
            "",
            "provider-x",
            "error without ticker",
            id="edge-case-empty-ticker",
        ),
    ],
)
def test_log_adapter_validation_edge_cases(ticker, provider_name, error_message):
    """Valida casos-limite para `_log_adapter_validation`.

    Casos testados: `provider_name` vazio e `ticker` vazio. Garante que
    `log_invalid_rows` é chamado e que o `reason_message` no registro
    corresponde à `error_message` fornecida.
    """

    # Arrange

    adapter = DummyAdapter()
    adapter.get_metadata = MagicMock(return_value={"provider": provider_name})
    exc = Exception(error_message)

    log_invalid_rows_mock = MagicMock()
    mock_validation_module = types.SimpleNamespace(
        log_invalid_rows=log_invalid_rows_mock,
    )
    log_context = {}

    with patch.dict(
        "sys.modules",
        {
            "src.validation": mock_validation_module,
        },
    ):
        # Act

        adapter._log_adapter_validation(exc, ticker, log_context)

    # Assert

    log_invalid_rows_mock.assert_called_once()
    call_kwargs = log_invalid_rows_mock.call_args.kwargs

    assert call_kwargs["provider"] == provider_name
    assert call_kwargs["ticker"] == ticker

    error_records = call_kwargs["error_records"]
    assert error_records[0]["reason_message"] == error_message


@pytest.mark.parametrize(
    "import_raises, log_invalid_rows_raises, expected_debug_call_msg",
    [
        pytest.param(
            True,
            False,
            "Adapter validation logging helper not available",
            id="error-case-import-fails",
        ),
        pytest.param(
            False,
            True,
            "Failed to write adapter validation to ingest_logs",
            id="error-case-log-invalid-rows-fails",
        ),
    ],
)
def test_log_adapter_validation_error_paths(
    import_raises, log_invalid_rows_raises, expected_debug_call_msg, caplog
):
    # Arrange

    adapter = DummyAdapter()
    adapter.get_metadata = MagicMock(return_value={"provider": "prov"})
    exc = Exception("boom")
    ticker = "XYZ"
    log_context = {}

    # Prepare import behavior without explicit conditionals using selection
    def fake_import(name, *args, **kwargs):
        def _raise_import(*a, **k):
            raise ImportError("cannot import")
        # If the import requested is "src.validation" simulate ImportError,
        # otherwise delegate to the real builtins.__import__ implementation.
        if name == "src.validation":
            return _raise_import(name, *args, **kwargs)

        return builtins.__import__(name, *args, **kwargs)

    log_invalid_rows_mock = MagicMock()
    # set side_effect conditionally via expression to avoid branching
    log_invalid_rows_mock.side_effect = (
        RuntimeError("write failed") if log_invalid_rows_raises else None
    )
    mock_validation_module = types.SimpleNamespace(
        log_invalid_rows=log_invalid_rows_mock,
    )

    # Select the appropriate patch context explicitly to avoid ambiguity
    import_ctx = (
        patch.dict(
            "sys.modules",
            {"src.validation": mock_validation_module},
        ),
        patch("builtins.__import__", side_effect=fake_import),
    )[import_raises]

    caplog.set_level(logging.DEBUG, logger=logger.name)

    with import_ctx:
        # Act

        adapter._log_adapter_validation(exc, ticker, log_context)

    # Assert

    # Assert the specific expected message depending on import behavior
    assert expected_debug_call_msg in caplog.text
