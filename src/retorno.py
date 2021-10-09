import numpy as np
import math

# Cálculo de retorno linear
import pandas as pd


def r_linear(p_fin, p_ini):
    return (p_fin/p_ini) - 1

# Cálculo de retorno logarítmico
def r_log(p_fin, p_ini):
    return np.log(p_fin / p_ini)

# Calcula o retorno logarítimo do período para cada ativo e retorna o retorno total e o retorno médio diário para
# entre os dias d_ini e d_fim
def retorno_periodo(_df):
    df = _df
    df['Retorno dia'] = r_log(df['Adj Close'], df['Adj Close'].shift(1))
    ret_periodo = df['Retorno dia'].sum()
    ret_medio = df['Retorno dia'].mean()
    desvio = df['Retorno dia'].std()
    return ret_periodo, ret_medio, desvio

# Converte o retorno entre períodos
def conv_retorno(rt_p, total_periodos):
    return ((1 + rt_p) ** total_periodos) - 1

# Converte o desvio padrão entre períodos
def conv_risco(ris_p, total_periodos):
    return ris_p * math.sqrt(total_periodos)

def coef_var(risco, ret_medio):
    return risco / ret_medio

#calcula correlacao entre dois lista de ativos usando o arquivo .csv localizado em dados
def correlacao(ativos):
    new_df = pd.DataFrame()
    for a in ativos:
        df1 = pd.read_csv(f"dados/{a}.csv")
        df1.rename({"Return": f"{a}"}, axis=1, inplace=True)
        ret_a = df1[f"{a}"]
        new_df[f"{a}"] = ret_a.copy()
    return new_df.corr(method="pearson")

