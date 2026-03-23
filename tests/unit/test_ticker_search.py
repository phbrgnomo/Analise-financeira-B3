from __future__ import annotations

import importlib

from src.search.ticker_search import find_best_match, suggest_tickers


def test_suggest_happy_path(sample_db, monkeypatch):
    # sample_db fixture contains PETR4 from sample_ticker.csv
    # monkeypatch db list to use the sample connection
    import src.db.prices as prices

    monkeypatch.setattr(prices, "list_price_tickers", lambda: ["PETR4", "ITUB3"])  # type: ignore

    results = suggest_tickers("petr")
    assert isinstance(results, list)
    assert "PETR4" in results


def test_empty_db(monkeypatch):
    import src.db.prices as prices

    monkeypatch.setattr(prices, "list_price_tickers", lambda: [])  # type: ignore
    assert suggest_tickers("anything") == []
    assert find_best_match("anything") is None


def test_fuzzywuzzy_unavailable_fallback(monkeypatch):
    # Simulate fuzzywuzzy not installed by reloading module with fake import
    # Remove fuzzywuzzy if present in sys.modules
    import sys

    orig = sys.modules.get("fuzzywuzzy")
    if "fuzzywuzzy" in sys.modules:
        sys.modules.pop("fuzzywuzzy")

    # reload the ticker_search module to force import-time detection
    ts_mod = importlib.reload(importlib.import_module("src.search.ticker_search"))

    # patch list_price_tickers
    import src.db.prices as prices

    monkeypatch.setattr(prices, "list_price_tickers", lambda: ["PETR4"])  # type: ignore

    # ensure module fell back to difflib by checking internal attr
    assert ts_mod._fuzzy_process is None

    # now call functions
    assert ts_mod.suggest_tickers("petr") == ["PETR4"]
    assert ts_mod.find_best_match("petr") == "PETR4"

    # restore fuzzywuzzy module if it was present
    if orig is not None:
        sys.modules["fuzzywuzzy"] = orig
