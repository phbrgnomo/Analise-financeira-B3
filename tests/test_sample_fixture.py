def test_sample_db_row_count(sample_db):
    """Verifica que o banco em memória foi populado com 5 linhas do CSV de exemplo."""
    cur = sample_db.cursor()
    cur.execute("SELECT COUNT(*) FROM prices")
    count = cur.fetchone()[0]
    assert count == 5


def test_sample_db_price_for_date(sample_db):
    """Consulta um preço conhecido no CSV para validar integridade dos dados."""
    cur = sample_db.cursor()
    cur.execute("SELECT close FROM prices WHERE date = ? LIMIT 1", ("2023-01-05",))
    row = cur.fetchone()
    assert row is not None
    assert abs(row[0] - 29.90) < 1e-6
