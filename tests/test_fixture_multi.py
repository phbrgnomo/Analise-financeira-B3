from tests.fixture_utils import parse_fixture_csv


def test_sample_ticker_multi_parsing():
    rows = parse_fixture_csv("sample_ticker_multi.csv")

    # Expect 5 data rows as provided in fixture
    assert len(rows) == 5

    tickers = [r[0] for r in rows]
    assert "VALE3.SA" in tickers
    # Ensure empty ticker row exists as edge case
    assert "" in tickers

    # Verify a numeric value parsed correctly for VALE3 on 2023-01-02
    found = [r for r in rows if r[0] == "VALE3.SA" and r[1] == "2023-01-02"]
    assert found, "VALE3.SA 2023-01-02 not found in fixture"
    assert abs(found[0][5] - 66.0) < 1e-9
