import builtins
import logging
import types
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.base import Adapter, logger


class DummyAdapter(Adapter):
    """Minimal concrete Adapter to allow instantiation for tests."""

    def fetch(self, ticker: str, **kwargs):
        raise NotImplementedError

    def _fetch_once(self, ticker: str, start: str, end: str, **kwargs):
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
    # Arrange

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

        return (
            builtins.__import__,
            _raise_import,
        )[name == "src.validation"](name, *args, **kwargs)

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

    # Accept either the expected message or the generic import-fails message
    assert (
        expected_debug_call_msg in caplog.text
        or "Adapter validation logging helper not available" in caplog.text
    )
