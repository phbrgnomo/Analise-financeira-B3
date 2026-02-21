import math
from typing import Tuple, Union

import numpy as np
import pandas as pd
from src.paths import DATA_DIR


def r_linear(
    p_fin: Union[float, int, pd.Series, np.ndarray],
    p_ini: Union[float, int, pd.Series, np.ndarray],
) -> Union[float, pd.Series]:
    """Calcula retorno linear (p_fin / p_ini) - 1.

    Suporta scalars e pandas Series/arrays.
    """
    return (p_fin / p_ini) - 1


def r_log(
    p_fin: Union[float, int, pd.Series, np.ndarray],
    p_ini: Union[float, int, pd.Series, np.ndarray],
) -> Union[float, pd.Series]:
    """Calcula retorno logarítmico: ln(p_fin / p_ini)."""
    return np.log(p_fin / p_ini)


def retorno_periodo(_df: pd.DataFrame) -> Tuple[float, float, float]:
    """Calcula retorno do período a partir de um DataFrame com coluna de preço.

    Retorna uma tupla: (retorno_total, retorno_medio_diario, desvio)
    """
    df = _df.copy()
    # Preferência por colunas ajustadas
    price_col = None
    for c in ("adj_close", "Adj Close", "close", "Close"):
        if c in df.columns:
            price_col = c
            break
    if price_col is None:
        raise KeyError("Nenhuma coluna de preço encontrada")

    df["Retorno dia"] = r_log(df[price_col], df[price_col].shift(1))
    ret_periodo = float(df["Retorno dia"].sum())
    ret_medio = float(df["Retorno dia"].mean())
    desvio = float(df["Retorno dia"].std())
    return ret_periodo, ret_medio, desvio


def conv_retorno(rt_p: float, total_periodos: int) -> float:
    """Converte retorno médio para retorno em outro período (ex.: anualização)."""
    return ((1 + rt_p) ** total_periodos) - 1


def conv_risco(ris_p: float, total_periodos: int) -> float:
    """Converte desvio padrão entre períodos usando raiz quadrada do tempo."""
    return ris_p * math.sqrt(total_periodos)


def coef_var(risco: float, ret_medio: float) -> float:
    """Coeficiente de variação (risco / retorno médio)."""
    return risco / ret_medio


def correlacao(ativos: list[str]) -> pd.DataFrame:
    """Calcula correlação entre ativos a partir dos arquivos CSV em `dados/`.

    Retorna um DataFrame de correlações (pearson).
    """
    new_df = pd.DataFrame()
    for a in ativos:
        try:
            fp = DATA_DIR / f"{a}.csv"
            df1 = pd.read_csv(fp)
        except (FileNotFoundError, OSError) as e:
            print(f"Dados de {a} não encontrados: {e}")
            continue
        df1.rename({"Return": f"{a}"}, axis=1, inplace=True)
        ret_a = df1[f"{a}"]
        new_df[f"{a}"] = ret_a.copy()
    return new_df.corr(method="pearson")
