import pandas as pd
import yfinance as yf

"""
Este módulo substitui o uso de `pandas_datareader` (incompatível com
Python 3.12) e oferece duas funções simples que retornam `pandas.DataFrame`
com OHLCV/adj close para um índice ou ativo.
"""


def cotacao_indice_dia(indice, data_inicio, data_fim) -> pd.DataFrame:
    # Coleta valores do OHLCV e Adj Close do <indice> entre <data_inicio> e <data_fim>
    ticker = f"^{indice}"
    print(f"Coletando dados do índice {indice} ({ticker})...")
    return yf.download(ticker, start=data_inicio, end=data_fim)


def cotacao_ativo_dia(ativo, data_inicio, data_fim) -> pd.DataFrame:
    # Coleta valores do OHLCV e Adj Close do <ativo> entre <data_inicio> e <data_fim>
    ticker = f"{ativo}.SA"
    print(f"Coletando dados do ativo {ativo} ({ticker})...")
    return yf.download(ticker, start=f"{data_inicio}", end=f"{data_fim}")
