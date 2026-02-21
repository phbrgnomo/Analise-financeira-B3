import math

import numpy as np

# Cálculo de retorno linear
import pandas as pd


def r_linear(p_fin, p_ini):
    return (p_fin / p_ini) - 1


# Cálculo de retorno logarítmico
def r_log(p_fin, p_ini):
    return np.log(p_fin / p_ini)


# Calcula o retorno logarítmico do período para cada ativo.
# Retorna: (retorno total, retorno médio diário, desvio) entre os dias d_ini e d_fim.
def retorno_periodo(_df):
    df = _df
    # Prefer `adj_close` when available; otherwise fall back to `close`.
    price_col = None
    for c in ("adj_close", "Adj Close", "close", "Close"):
        if c in df.columns:
            price_col = c
            break
    if price_col is None:
        raise KeyError(
            "Nenhuma coluna de preço encontrada (esperado 'close' ou 'adj_close')"
        )

    df["Retorno dia"] = r_log(df[price_col], df[price_col].shift(1))
    ret_periodo = df["Retorno dia"].sum()
    ret_medio = df["Retorno dia"].mean()
    desvio = df["Retorno dia"].std()
    return ret_periodo, ret_medio, desvio


# Converte o retorno entre períodos
def conv_retorno(rt_p, total_periodos):
    return ((1 + rt_p) ** total_periodos) - 1


# Converte o desvio padrão entre períodos
def conv_risco(ris_p, total_periodos):
    return ris_p * math.sqrt(total_periodos)


def coef_var(risco, ret_medio):
    return risco / ret_medio


# Calcula correlação entre uma lista de ativos usando CSVs em `dados/`.
def correlacao(ativos):
    new_df = pd.DataFrame()
    for a in ativos:
        try:
            df1 = pd.read_csv(f"dados/{a}.csv")
        except (FileNotFoundError, OSError) as e:
            print(f"Dados de {a} não encontrados: {e}")
            continue
        df1.rename({"Return": f"{a}"}, axis=1, inplace=True)
        ret_a = df1[f"{a}"]
        new_df[f"{a}"] = ret_a.copy()
    return new_df.corr(method="pearson")
