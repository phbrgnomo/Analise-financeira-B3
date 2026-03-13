"""
Small script example for consumers showing how to read `returns` and
compute cumulative return.
"""

import logging
import sqlite3
from contextlib import closing

import pandas as pd

logger = logging.getLogger(__name__)


def main(db_path: str = "dados/data.db", ticker: str = "PETR4.SA"):
    """Read returns for `ticker` from `db_path` and print cumulative return.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file (default: "dados/data.db").
    ticker : str
        Ticker symbol to query (default: "PETR4.SA").

    Raises
    ------
    RuntimeError
        If reading from the database fails.
    ValueError
        If no rows are found for the provided `ticker` in the `returns` table.
    """
    # Ensure the DB connection is closed after use to release file handles.
    with closing(sqlite3.connect(db_path)) as conn:
        try:
            sql = (
                "SELECT date, return_value FROM returns WHERE ticker = ? ORDER BY date"
            )
            df = pd.read_sql_query(
                sql,
                conn,
                params=(ticker,),
                parse_dates=["date"],
            ).set_index("date")
        except Exception as exc:
            logger.exception("Falha ao ler 'returns' para %s", ticker)
            raise RuntimeError(f"Falha ao ler 'returns' para {ticker}") from exc

        if df.empty:
            msg = f"Nenhum dado na tabela 'returns' para o ticker {ticker}"
            logger.warning(msg)
            raise ValueError(msg)

        # calcula retorno acumulado: transforma cada retorno em fator de
        # crescimento (1 + return_value), aplica produto acumulado e subtrai 1
        # para converter de volta em porcentagem acumulada.
        df["cumulative_return"] = (1 + df["return_value"]).cumprod() - 1
        print(df.tail())


if __name__ == "__main__":
    main()
