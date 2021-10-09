import src.dados_b3 as dados
import src.retorno as rt

import pandas as pd
import os
import numpy as np


if __name__ == '__main__':
    # ativos_entrada = input("Lista de Ativos, separados por vírgula (exemplo: PETR4,BBDC3): ")
    # ativos = ativos_entrada.split(',')
    # data_in = input("Data de inicio (MM-DD-AAAA): ")
    # data_fim = input("Data de fim (MM-DD-AAAA): ")

    ativos = ['PETR4', 'ITUB3', 'BBDC4', 'VALE3', 'WIZS3']
    d_in = '01-01-2021'
    d_fim = '09-30-2021'

    for a in ativos:
        # Verifica se os arquivo já existem
        # {TODO} adicionar verificação se os dados correspondem às datas solicitadas
        if os.path.isfile(f"dados/{a}.csv"):
            print(f"Dados encontrados para {a}")
            continue
        # Se os dados não existirem, realiza o download
        print(f"Baixando dados de {a}")
        df = dados.cotacao_ativo_dia(a, d_in, d_fim)
        # Calcula o retorno
        print(f"Calculado retornos de {a}")
        df['Return'] = rt.r_log(df['Adj Close'], df['Adj Close'].shift(1))
        # Salva dados em .csv
        df.to_csv(f"dados/{a}.csv")

    for a in ativos:
        # Abre o arquivo de dados
        df = pd.read_csv(f"dados/{a}.csv")
        retorno_total = df['Return'].sum()
        retorno_medio = df['Return'].mean()
        risco = df['Return'].std()
        retorno_anual = rt.conv_retorno(retorno_medio, 252)
        risco_anual = rt.conv_risco(risco, 252)

        print(f"\n--------{a}--------")
        print(f"Retorno total do período: {round((retorno_total * 100), 4)}%")
        print(f"Retorno médio ao dia: {round((retorno_medio * 100), 4)}%")
        print(f"Risco ao dia: {round((risco * 100), 4)}%")
        print(f"Retorno médio ao ano: {round((retorno_anual * 100), 4)}%")
        print(f"Risco ao ano: {round(risco_anual * 100, 4)}%")
        print(f"Coeficiente de variação(dia):{rt.coef_var(risco, retorno_medio)}")

        # Calcula projeção de faixa de expectativa de retorno
        ultimo_preco = round(df.tail(1).values[0][6], 2)
        proj_preco = ultimo_preco * (1 + retorno_anual)
        print('\nProjeçoes para o 1 ano:')
        print(f"Ultimo Preco: {ultimo_preco}")
        print(f"Retorno máximo: {round(((retorno_anual + risco_anual) * 100), 4)}%")
        print(f"Preço máximo: {proj_preco * (1 + risco_anual)}")
        print(f"Retorno mínimo: {round(((retorno_anual - risco_anual) * 100), 4)}%")
        print(f"Preço mínimo: {proj_preco * (1 - risco_anual)}")

    # Calcula correlação entre os ativos
    newdf = rt.correlacao(ativos)
    print(newdf)