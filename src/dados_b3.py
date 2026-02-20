import yfinance as yf


def cotacao_indice_dia(indice, data_inicio, data_fim):
    # Coleta valores do OHLCV e Adj Close do <indice> entre <data_inicio> e <data_fim>
    ticker = f"^{indice}"
    print(f"Coletando dados do índice {indice} ({ticker})...")
    return yf.download(ticker, start=f"{data_inicio}", end=f"{data_fim}")


def cotacao_ativo_dia(ativo, data_inicio, data_fim):
    # Coleta valores do OHLCV e Adj Close do <ativo> entre <data_inicio> e <data_fim>
    ticker = f"{ativo}.SA"
    print(f"Coletando dados do ativo {ativo} ({ticker})...")
    return yf.download(ticker, start=f"{data_inicio}", end=f"{data_fim}")
