from pandas_datareader import data as web


def cotacao_indice_dia(indice, data_inicio, data_fim):
    # Coleta valores do OHLCV e Adj Close do <indice> entre <data_inicio> e <data_fim>
    print(f"Coletando dados do índice {indice}...")
    return web.DataReader(
        f'^{indice}',
        data_source='yahoo',
        start=f'{data_inicio}',
        end=f'{data_fim}',
    )


def cotacao_ativo_dia(ativo, data_inicio, data_fim):
    # Coleta valores do OHLCV e Adj Close do <ativo> entre <data_inicio> e <data_fim>
    print(f"Coletando dados do ativo {ativo}...")
    return web.DataReader(
        f'{ativo}.SA',
        data_source='yahoo',
        start=f'{data_inicio}',
        end=f'{data_fim}',
    )
