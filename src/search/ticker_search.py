"""Fuzzy search helpers for ticker lookup.

Provide a small public API for suggesting tickers from the prices DB and for
finding the single best match. The implementation prefers fuzzywuzzy when
available and falls back to difflib.get_close_matches otherwise.

The functions call src.db.prices.list_price_tickers() to obtain candidates
and reuse src.tickers.normalize_b3_ticker for normalization when returning
matches.
"""

from __future__ import annotations

import difflib
import importlib
from typing import Any, Iterable, List, Optional

import src.db.prices as _prices
from src.tickers import normalize_b3_ticker

# Try to resolve fuzzywuzzy at runtime without a static import so type checkers
# won't report a missing third-party module when it's not installed.
_fuzzy_process: Any = None
try:
    _mod = importlib.import_module("fuzzywuzzy.process")
    _fuzzy_process = getattr(_mod, "process", _mod)
except Exception:  # pragma: no cover - exercised by tests via import-time sim
    _fuzzy_process = None


def _normalize_candidates(candidates: Iterable[str]) -> List[str]:
    # Ensure tickers are in base B3 normalized form for matching
    out: List[str] = []
    for c in candidates:
        try:
            out.append(normalize_b3_ticker(c))
        except Exception:
            # if normalization fails, keep the original upper-stripped value
            out.append(str(c).strip().upper().removesuffix(".SA"))
    return sorted(set(out))


def suggest_tickers(query: str, limit: int = 20) -> List[str]:
    """Return a list of suggested tickers similar to ``query``.

    Parameters
    ----------
    query: str
        Partial or full ticker/name to search for.
    limit: int
        Maximum number of suggestions to return.

    Returns
    -------
    list[str]
        List of normalized tickers present in the prices DB that best match
        the query. Returns an empty list when the DB has no tickers.
    """
    if not isinstance(query, str) or not query.strip():
        return []

    candidates = _prices.list_price_tickers()
    if not candidates:
        return []

    norm_candidates = _normalize_candidates(candidates)
    q = query.strip().upper()

    if _fuzzy_process is not None:
        results = _fuzzy_process.extract(q, norm_candidates, limit=limit)
        # extract returns tuples (match, score, index) for some versions;
        # be defensive and accept (match, score) as well.
        matches: List[str] = []
        for item in results:
            if isinstance(item, tuple):
                matches.append(item[0])
            else:
                matches.append(str(item))
        return matches[:limit]

    # fallback to difflib
    matches = difflib.get_close_matches(q, norm_candidates, n=limit, cutoff=0.0)
    return matches


def find_best_match(query: str, threshold: float = 0.7) -> Optional[str]:
    """Find the single best ticker matching ``query``.

    Returns the normalized ticker when a match is above ``threshold`` or
    ``None`` otherwise.
    """
    if not isinstance(query, str) or not query.strip():
        return None

    candidates = _prices.list_price_tickers()
    if not candidates:
        return None

    norm_candidates = _normalize_candidates(candidates)
    q = query.strip().upper()

    if _fuzzy_process is not None:
        best = _fuzzy_process.extractOne(q, norm_candidates)
        if not best:
            return None
        # best is (match, score, index) or (match, score)
        match = best[0]
        score = float(best[1])
        if score / 100.0 >= float(threshold):
            return match
        return None

    # difflib returns close matches but with no explicit score; emulate
    matches = difflib.get_close_matches(q, norm_candidates, n=1, cutoff=0.0)
    if not matches:
        return None
    # Use SequenceMatcher to compute ratio
    ratio = difflib.SequenceMatcher(a=q, b=matches[0]).ratio()
    if ratio >= float(threshold):
        return matches[0]
    return None
