from src.dados_b3 import cotacao_ativo_dia
import src.retorno as retorno
import matplotlib.pyplot as plt


if __name__ == '__main__':
    # ativos_entrada = input("Lista de Ativos, separados por vírgula (exemplo: PETR4,BBDC3): ")
    # ativos = ativos_entrada.split(',')
    # data_in = input("Data de inicio (MM-DD-AAAA): ")
    # data_fim = input("Data de fim (MM-DD-AAAA): ")

    ativos = ['PETR4', 'VALE3']
    data_in = '01-01-2021'
    data_fim = '09-30-2021'

    for a in ativos:
        df = cotacao_ativo_dia(a, data_in, data_fim)
        df['Retorno dia'] = retorno.log(df['Adj Close'], df['Adj Close'].shift(1))
        ret_periodo = df['Retorno dia'].sum()
        ret_medio = df['Retorno dia'].mean()
        # df['Retorno dia'].plot()
        # plt.show()
        print(df)
        print(f"Retorno total do período para {a}: {round((ret_periodo * 100), 4)}%")
        print(f"Retorno médio diário para {a}: {round((ret_medio * 100), 4)}%")


