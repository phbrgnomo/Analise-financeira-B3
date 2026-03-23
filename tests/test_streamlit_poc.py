"""Smoke tests for the Streamlit POC app.

These are lightweight, import-safe tests that exercise the importability
of the module and the data-loading helpers without running Streamlit.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def test_import_module():
    # ensure module is importable (syntax errors would fail here)
    import importlib

    importlib.import_module("src.apps.streamlit_poc")


def test_load_prices_with_fixture(sample_db):
    # Use the sample_db fixture which provides an in-memory DB seeded with
    # tests/fixtures/sample_ticker.csv. Pass a short date range and assert a
    # DataFrame is returned.
    from src.apps.streamlit_poc import load_prices

    start = date(2023, 1, 1)
    end = date(2023, 12, 31)

    df = load_prices("PETR4", start=start, end=end)

    assert isinstance(df, pd.DataFrame)


def test_empty_state_handling(monkeypatch):
    """When the DB returns an empty DataFrame, load_prices must return an
    empty DataFrame and _safe_line_chart must not raise when called with it.
    """
    from src.apps import streamlit_poc

    # monkeypatch the DB layer: make read_prices return an empty DataFrame
    monkeypatch.setattr("src.db.prices.read_prices", lambda *a, **k: pd.DataFrame())

    df = streamlit_poc.load_prices("FAKE", start=None, end=None)
    assert isinstance(df, pd.DataFrame)
    assert df.empty

    # _safe_line_chart should exit cleanly with empty DataFrame
    streamlit_poc._safe_line_chart(df)
