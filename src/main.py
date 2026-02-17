"""Entry point CLI for the project.

Provides a minimal CLI that supports `--help` and an optional `--quickstart`
flag to run a small quickstart analysis used by early acceptance tests.
"""

from datetime import date, timedelta
import argparse
import os
from typing import List

import pandas as pd

import src.dados_b3 as dados
import src.retorno as rt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main", description="Analise financeira B3 CLI"
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument(
        "--quickstart",
        action="store_true",
        help="Run a small quickstart analysis for example tickers",
    )
    return parser


def run_quickstart(tickers: List[str] | None = None) -> None:
    if tickers is None:
        tickers = ["PETR4", "ITUB3", "BBDC4", "VALE3", "WIZS3", "ECOR3"]

    d_atual = date.today()
    periodo_dados = 52
    time_skew = timedelta(weeks=periodo_dados)

    d_fim = d_atual.strftime("%m-%d-%Y")
    d_in = (d_atual - time_skew).strftime("%m-%d-%Y")

    for a in tickers:
        if os.path.isfile(f"dados/{a}.csv"):
            print(f"Dados encontrados para {a}")
            continue

        print(f"Baixando dados de {a}")
        try:
            df = dados.cotacao_ativo_dia(a, d_in, d_fim)
        except Exception:
            print("Problemas baixando dados")
            continue

        print(f"Calculado retornos de {a}")
        df["Return"] = rt.r_log(df["Adj Close"], df["Adj Close"].shift(1))
        df.to_csv(f"dados/{a}.csv")

    for a in tickers:
        try:
            df = pd.read_csv(f"dados/{a}.csv")
        except Exception:
            print(f"Dados para {a} não encontrados")
            continue

        retorno_medio = df["Return"].mean()
        risco = df["Return"].std()
        retorno_anual = rt.conv_retorno(retorno_medio, 252)
        risco_anual = rt.conv_risco(risco, 252)

        print(f"\n--------{a}--------")
        print(f"Retorno médio ao dia: {round((retorno_medio * 100), 4)}%")
        print(f"Risco ao dia: {round((risco * 100), 4)}%")
        print(f"Retorno médio ao ano: {round((retorno_anual * 100), 4)}%")
        print(f"Risco ao ano: {round(risco_anual * 100, 4)}%")
        print(f"Coeficiente de variação(dia):{rt.coef_var(risco, retorno_medio)}")

    newdf = rt.correlacao(tickers)
    print(newdf)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print("analise-financeira-b3 0.1.0")
        return

    if args.quickstart:
        run_quickstart()


if __name__ == "__main__":
    main()
