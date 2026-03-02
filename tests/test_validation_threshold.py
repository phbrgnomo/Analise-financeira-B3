import os

import pytest

from src.validation.core import _normalize_threshold_value


@pytest.mark.parametrize(
    "input_value,expected",
    [
        (0.2, 0.2),
        ("0.2", 0.2),
        (50, 0.50),  # numeric >1 treated as percent
        (10, 0.10),
        ("10%", 0.10),
    ],
)
def test_normalize_threshold_strict_valid_values(input_value, expected):
    """Verify that valid threshold inputs normalize to expected numeric values."""
    assert _normalize_threshold_value(input_value, source="arg") == pytest.approx(expected)


@pytest.mark.parametrize(
    "bad",
    [None, -0.1, 200, "foo", "1e100"],
)
def test_normalize_threshold_strict_invalid_raises(bad):
    """Verify that invalid threshold inputs raise a ValueError."""
    # values that normalize within [0,1] are allowed; others should fail
    with pytest.raises(ValueError):
        _normalize_threshold_value(bad, source="arg")


def test_normalize_threshold_env_default(monkeypatch, caplog):
    monkeypatch.delenv("VALIDATION_INVALID_PERCENT_THRESHOLD", raising=False)

    with caplog.at_level("WARNING"):
        val = _normalize_threshold_value(None, source="env")
    assert val == pytest.approx(0.10)
    assert "No threshold provided" in caplog.text


def test_normalize_threshold_env_invalid(monkeypatch, caplog):
    monkeypatch.setenv("VALIDATION_INVALID_PERCENT_THRESHOLD", "foo")
    with caplog.at_level("WARNING"):
        val = _normalize_threshold_value("foo", source="env")
    assert val == pytest.approx(0.10)
    assert "Invalid threshold" in caplog.text or "Could not parse" in caplog.text


def test_normalize_threshold_env_percentage(monkeypatch, caplog):
    _run_normalize_threshold_env_test(monkeypatch, "10", caplog, 0.10)
    _run_normalize_threshold_env_test(monkeypatch, "25%", caplog, 0.25)


def _run_normalize_threshold_env_test(monkeypatch, value, caplog, expected):
    """Helper: set environment value, run normalization and assert result."""
    monkeypatch.setenv("VALIDATION_INVALID_PERCENT_THRESHOLD", value)
    with caplog.at_level("WARNING"):
        # call through env style by passing the env string
        val = _normalize_threshold_value(
            os.getenv("VALIDATION_INVALID_PERCENT_THRESHOLD"), source="env"
        )
    assert val == pytest.approx(expected)
    assert "normalized to" in caplog.text
