"""Low-level shared utilities for the db package.

Contains pure helpers that have no dependency on other ``src.db`` sub-modules,
avoiding circular imports.
"""

import hashlib
import re
import sqlite3

import pandas as pd

from src.tickers import normalize_b3_ticker
from src.time_utils import now_utc_iso


def _build_row_tuple(vals: dict, schema_cols: list) -> tuple:
    return tuple(vals.get(col) for col in schema_cols)


# Identifier helpers lifted to module level so read and write paths share the
# same validation and quoting rules. Keeps SQL construction robust against
# reserved words or unexpected characters in schema-derived column names.
def _is_valid_identifier(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))


def _quote_identifier(name: str) -> str:
    if not _is_valid_identifier(name):
        raise ValueError(f"Invalid column identifier: {name!r}")
    return f'"{name}"'


def _sqlite_version_tuple() -> tuple[int, ...]:
    """Parse ``sqlite3.sqlite_version`` into a tuple of integers.

    Handles non-numeric suffixes like ``"3.44.0-alpha"`` by consuming only
    the leading digit characters of each version component. Returns a
    tuple of ints (e.g., ``(3, 44, 0)``) and stops parsing when a component
    has no leading digits.
    """
    parts: list[int] = []
    for part in sqlite3.sqlite_version.split("."):
        numeric = ""
        for ch in part:
            if ch.isdigit():
                numeric += ch
            else:
                break
        if not numeric:
            break
        parts.append(int(numeric))
    return tuple(parts)


def _normalize_db_ticker(ticker: str) -> str:
    """Canonicaliza ticker para uso interno no banco.

    Atualmente a lógica espelha :func:`~src.tickers.normalize_b3_ticker` e
    garante que ``.SA`` seja removido, devolvendo sempre a forma base B3.
    """
    try:
        # reuse centralizada para evitar divergências
        return normalize_b3_ticker(ticker)
    except Exception:
        # em caso de entrada inválida, caímos em fallback semelhante ao
        # comportamento histórico, mas o valor resultante não é mais
        # validado pelo regex do normalize_b3_ticker.
        return ticker.strip().upper().removesuffix(".SA")


def _row_tuple_from_series(
    idx, row, ticker, source, fetched_at, cols_map, schema_cols
) -> tuple:
    date_s = pd.to_datetime(idx).strftime("%Y-%m-%d")
    normalized_ticker = _normalize_db_ticker(ticker)
    vals = {
        "ticker": normalized_ticker,
        "date": date_s,
        "source": source,
    }

    src_col = cols_map.get("source")
    if src_col is not None and not pd.isna(row[src_col]):
        vals["source"] = str(row[src_col])

    for name in ["open", "high", "low", "close", "volume"]:
        col = cols_map.get(name)
        if col is not None and not pd.isna(row[col]):
            vals[name] = float(row[col]) if name != "volume" else int(row[col])
        else:
            vals[name] = None

    payload = (
        f"{normalized_ticker}|{date_s}|{vals.get('open')}|{vals.get('high')}|"
        f"{vals.get('low')}|{vals.get('close')}|{vals.get('volume')}|{source}"
    )

    vals["raw_checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    vals["fetched_at"] = fetched_at or now_utc_iso()

    return _build_row_tuple(vals, schema_cols)
