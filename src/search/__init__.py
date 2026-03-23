"""Search helpers package.

Expose a tiny public API for ticker fuzzy search used by the CLI and tests.
"""

from __future__ import annotations

from .ticker_search import find_best_match, suggest_tickers

__all__ = ["suggest_tickers", "find_best_match"]
