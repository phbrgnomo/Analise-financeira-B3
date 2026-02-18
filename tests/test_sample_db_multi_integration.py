import csv
import os
import sqlite3


def _fixture_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


def test_sample_db_multi_integration():
    # Create in-memory DB and populate from sample_ticker_multi.csv
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

    path = _fixture_path("sample_ticker_multi.csv")
    with open(path, newline="") as f:
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

    sql = (
        "INSERT INTO prices (ticker,date,open,high,low,close,adj_close,volume,source)"
        " VALUES (?,?,?,?,?,?,?,?,?)"
    )
    cur.executemany(sql, rows)
    db.commit()

    # Basic assertions
    cur.execute("SELECT COUNT(*) FROM prices")
    total = cur.fetchone()[0]
    assert total == 5

    # Distinct tickers (including empty ticker)
    cur.execute("SELECT DISTINCT ticker FROM prices")
    distinct = {r[0] for r in cur.fetchall()}
    assert "PETR4.SA" in distinct
    assert "VALE3.SA" in distinct
    assert "" in distinct

    # Query a known value
    cur.execute(
        "SELECT close FROM prices WHERE ticker = ? AND date = ?",
        ("VALE3.SA", "2023-01-02"),
    )
    val = cur.fetchone()
    assert val is not None
    assert abs(val[0] - 66.0) < 1e-9

    db.close()
