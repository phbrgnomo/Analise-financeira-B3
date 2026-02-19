"""Coleta de preços usando `yfinance` como provider primário.

Este módulo substitui o uso de `pandas_datareader` (incompatível com
Python 3.12) e oferece duas funções simples que retornam `pandas.DataFrame`
com OHLCV/adj close para um índice ou ativo.
"""
from typing import Any

import yfinance as yf


def cotacao_indice_dia(indice: str, data_inicio: str, data_fim: str) -> Any:
    """Coleta valores OHLCV/Adj Close do índice `^<indice>` entre as datas.

    Retorna o DataFrame provido por `yfinance.download`.
    """
    ticker = f"^{indice}"
    print(f"Coletando dados do índice {indice} ({ticker})...")
    return yf.download(ticker, start=data_inicio, end=data_fim)

def cotacao_ativo_dia(ativo: str, data_inicio: str, data_fim: str) -> Any:
    """Coleta valores OHLCV/Adj Close do ativo `<ativo>.SA` entre as datas."""
    ticker = f"{ativo}.SA"
    print(f"Coletando dados do ativo {ativo} ({ticker})...")
    return yf.download(ticker, start=data_inicio, end=data_fim)
