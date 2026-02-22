import csv
import os
import sqlite3


def parse_fixture_csv(filename: str):
    """
    The function `parse_fixture_csv` reads a fixture CSV file and returns a list of
    tuples containing data for database insertion.

    :param filename: The `parse_fixture_csv` function takes a `filename` parameter,
    which is a string representing the name of the CSV file to be parsed. The function
    reads the CSV file located in the "fixtures" directory relative to the current
    script's location.
    :type filename: str
    :return: The function `parse_fixture_csv` returns a list of tuples containing data
    parsed from a fixture CSV file. Each tuple represents a row of data in the same
    order as the columns in the `prices` table. The tuples contain information such as
    ticker symbol, date, open price, high price, low price, close price, adjusted close
    price, volume, and data source for each row in the CSV.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows.extend(
                (
                    r.get("ticker"),
                    r.get("date"),
                    float(r.get("open") or 0),
                    float(r.get("high") or 0),
                    float(r.get("low") or 0),
                    float(r.get("close") or 0),
                    int(r.get("volume") or 0),
                    r.get("source"),
                )
                for r in reader
            )
    return rows


def create_prices_db_from_rows(rows):
    """Create an in-memory SQLite DB, create `prices` table and insert rows.

    Returns a sqlite3.Connection object.
    """
    db = sqlite3.connect(":memory:")
    cur = db.cursor()
    cur.execute(
        """
        CREATE TABLE prices (
            ticker TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            source TEXT
        )
        """
    )

    sql = (
        "INSERT INTO prices (ticker,date,open,high,low,close,volume,source)"
        " VALUES (?,?,?,?,?,?,?,?)"
    )
    cur.executemany(sql, rows)
    db.commit()
    return db


def create_prices_db_from_csv(filename: str):
    rows = parse_fixture_csv(filename)
    return create_prices_db_from_rows(rows)


def get_or_make_snapshot_dir(env_path: str | None, tmp_path_factory) -> str:
    """Retorna um diretório absoluto para armazenar snapshots.

    - Se ``env_path`` for uma string não-None, garante que o diretório exista e
        retorna o caminho absoluto.
    - Caso contrário, usa ``tmp_path_factory`` para criar um diretório temporário
        e retorna seu caminho como string.
    """
    if env_path:
        os.makedirs(env_path, exist_ok=True)
        return os.path.abspath(env_path)
    d = tmp_path_factory.mktemp("snapshots")
    return str(d)
