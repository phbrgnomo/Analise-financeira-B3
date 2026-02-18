def test_sample_db_multi_integration(sample_db_multi):
    db = sample_db_multi
    cur = db.cursor()

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
