import csv
import os


def _fixture_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


def test_sample_ticker_multi_parsing():
    path = _fixture_path("sample_ticker_multi.csv")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Expect 5 data rows as provided in fixture
    assert len(rows) == 5

    tickers = [r.get("ticker") for r in rows]
    assert "VALE3.SA" in tickers
    # Ensure empty ticker row exists as edge case
    assert "" in tickers

    # Verify a numeric value parsed correctly for VALE3 on 2023-01-02
    found = [
        r
        for r in rows
        if r.get("ticker") == "VALE3.SA" and r.get("date") == "2023-01-02"
    ]
    assert found, "VALE3.SA 2023-01-02 not found in fixture"
    assert float(found[0]["close"]) == 66.0
