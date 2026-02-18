import csv
import os
import sqlite3


def parse_fixture_csv(filename: str):
    """Parse a fixture CSV into a list of tuples ready for DB insert.

    Returns tuples in the same order used by the `prices` table.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                (
                    r.get("ticker"),
                    r.get("date"),
                    float(r.get("open") or 0),
                    float(r.get("high") or 0),
                    float(r.get("low") or 0),
                    float(r.get("close") or 0),
                    float(r.get("adj_close") or 0),
                    int(r.get("volume") or 0),
                    r.get("source"),
                )
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
            adj_close REAL,
            volume INTEGER,
            source TEXT
        )
        """
    )

    sql = (
        "INSERT INTO prices (ticker,date,open,high,low,close,adj_close,volume,source)"
        " VALUES (?,?,?,?,?,?,?,?,?)"
    )
    cur.executemany(sql, rows)
    db.commit()
    return db


def create_prices_db_from_csv(filename: str):
    rows = parse_fixture_csv(filename)
    return create_prices_db_from_rows(rows)
