import sqlite3

import pytest

from tests.fixture_utils import parse_fixture_csv


@pytest.fixture(scope="function")
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

    rows = parse_fixture_csv("sample_ticker.csv")
    sql = (
        "INSERT INTO prices (ticker,date,open,high,low,close,adj_close,volume,source)"
        " VALUES (?,?,?,?,?,?,?,?,?)"
    )
    cur.executemany(sql, rows)
    db.commit()

    try:
        yield db
    finally:
        # Ensure the connection is always closed after each test
        db.close()
