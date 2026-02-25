"""Small script example for consumers showing how to read `returns` and compute cumulative return."""
import sqlite3
from contextlib import closing

import pandas as pd


def main(db_path: str = "dados/data.db", ticker: str = "PETR4.SA"):
    # Ensure the DB connection is closed after use to release file handles.
    with closing(sqlite3.connect(db_path)) as conn:
        df = pd.read_sql_query(
            "SELECT date, return FROM returns WHERE ticker = ? ORDER BY date",
            conn,
            params=(ticker,),
            parse_dates=["date"],
        ).set_index("date")

        df["cumulative_return"] = (1 + df["return"]).cumprod() - 1
        print(df.tail())


if __name__ == "__main__":
    main()
