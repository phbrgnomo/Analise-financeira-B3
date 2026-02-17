import os
import csv
import sqlite3
import pytest


def _get_fixture_path(filename: str) -> str:
    base = os.path.join(os.path.dirname(__file__), "fixtures")
    return os.path.join(base, filename)


@pytest.fixture
def sample_db():
    """Creates an in-memory SQLite DB seeded with tests/fixtures/sample_ticker.csv

    Yields a `sqlite3.Connection` object that tests can use.
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

    csv_path = _get_fixture_path("sample_ticker.csv")
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = []
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
    cur.executemany(
        "INSERT INTO prices (ticker,date,open,high,low,close,adj_close,volume,source) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    db.commit()

    yield db

    db.close()
