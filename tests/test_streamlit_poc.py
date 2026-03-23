"""Smoke tests for streamlit_poc module.

These tests verify that the streamlit_poc module can be imported and that
its functions work with a sample in-memory DB without requiring network calls.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from src.apps.streamlit_poc import _safe_line_chart, load_prices
from tests.conftest import create_prices_db_from_csv


@pytest.fixture
def db_with_data():
    """Create an in-memory SQLite DB seeded with sample_ticker.csv."""
    conn = create_prices_db_from_csv("sample_ticker.csv")
    yield conn
    conn.close()


def test_load_prices_returns_dataframe(db_with_data):
    """Verify load_prices returns a DataFrame (type check)."""
    with patch("src.db.connection.connect", return_value=db_with_data):
        result = load_prices("PETR4", date(2023, 1, 1), date(2023, 12, 31))
    assert isinstance(result, pd.DataFrame)


def test_load_prices_empty_for_unknown_ticker(db_with_data):
    """Verify load_prices returns a DataFrame for unknown ticker."""
    with patch("src.db.connection.connect", return_value=db_with_data):
        result = load_prices("UNKNOWN", date(2023, 1, 1), date(2023, 12, 31))
    assert isinstance(result, pd.DataFrame)


def test_safe_line_chart_accepts_series():
    """Verify _safe_line_chart works when given a pandas Series."""
    series = pd.Series([1.0, 2.0, 3.0], name="values")
    _safe_line_chart(series, label="test")


def test_safe_line_chart_accepts_dataframe():
    """Verify _safe_line_chart works when given a pandas DataFrame."""
    df = pd.DataFrame({"price": [100.0, 101.0, 102.0]})
    _safe_line_chart(df, label="price")


def test_safe_line_chart_empty_handling():
    """Verify _safe_line_chart handles empty data gracefully."""
    empty_series = pd.Series([], dtype=float)
    _safe_line_chart(empty_series, label="empty")
