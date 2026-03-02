"""Helpers para normalização e validação de tickers B3.

Este módulo centraliza regras de entrada da CLI para evitar divergências entre
comandos (`run`, `compute-returns`, `pipeline ingest`).
"""

from __future__ import annotations

import re

_B3_TICKER_PATTERN = re.compile(r"^[A-Z0-9]{4,8}$")


def normalize_b3_ticker(ticker: str) -> str:
    """Normaliza ticker no padrão B3 sem sufixo de provider.

    Exemplos válidos: ``PETR4``, ``ITUB3``, ``BOVA11``, ``MGLU3``.
    Também aceita entrada com ``.SA`` por compatibilidade e remove o sufixo.
    """
    if not isinstance(ticker, str):
        raise ValueError("ticker must be a string")

    candidate = ticker.strip().upper()
    if not candidate:
        raise ValueError("ticker cannot be empty")

    if candidate.endswith(".SA"):
        candidate = candidate[:-3]

    if not _B3_TICKER_PATTERN.match(candidate):
        raise ValueError(
            "ticker inválido; use padrão B3 (ex.: PETR4, ITUB4, BOVA11)"
        )

    if not any(char.isdigit() for char in candidate):
        raise ValueError(
            "ticker inválido; deve conter dígitos (ex.: PETR4, BOVA11)"
        )

    return candidate


def to_provider_ticker(ticker: str) -> str:
    """Converte ticker B3 para formato esperado por provedores Yahoo-like."""
    return f"{normalize_b3_ticker(ticker)}.SA"


def ticker_variants(ticker: str) -> tuple[str, str]:
    """Gera duas formas de um ticker B3 para consulta no banco.

    Normaliza a entrada usando :func:`normalize_b3_ticker` e produz uma tupla
    contendo:

    * o ticker base (ex.: ``"ABCD"``)
    * a variante adicionando o sufixo ``.SA`` (ex.: ``"ABCD.SA"``)

    Exemplos::

        >>> ticker_variants("ABCD")
        ("ABCD", "ABCD.SA")
        >>> ticker_variants("abcd")
        ("ABCD", "ABCD.SA")

    Parameters
    ----------
    ticker: str
        Valor de entrada que será normalizado.

    Returns
    -------
    tuple[str, str]
        Par de variantes (base, com sufixo)."""
    base = normalize_b3_ticker(ticker)
    return base, f"{base}.SA"
