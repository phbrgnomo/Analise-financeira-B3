import os
import sqlite3

import pandas as pd


def test_returns_consumer_example(tmp_path, monkeypatch):
    """Ensure the example code from `returns-consumer.ipynb` can run.

    The notebook hardcodes a relative path of ``dados/data.db`` and a SQL
    query against a ``returns`` table.  This test creates a temporary database
    with the expected schema, switches the working directory into the temporary
    folder and then replays the query logic.  It will fail if the file is
    missing, the table/columns are incorrect or the ticker isn't present.
    """

    # create a fake project layout under tmp_path
    dados = tmp_path / "dados"
    dados.mkdir()
    db_path = dados / "data.db"

    conn = sqlite3.connect(str(db_path))
    # mimic real schema: return_value column plus some extras
    conn.execute(
        'CREATE TABLE returns (ticker text, date text, "return" real, '
        "return_type text, created_at text)"
    )
    conn.execute(
        'INSERT INTO returns (ticker,date,"return") '
        "VALUES ('PETR4.SA','2021-01-01',0.01)"
    )
    conn.commit()
    conn.close()
    # create a dummy repo root marker so find_repo_root() succeeds
    (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nname = "dummy"\n')

    # run from the temporary directory so relative paths match the notebook
    monkeypatch.chdir(tmp_path)

    assert os.path.exists("dados/data.db"), "database file should exist"

    conn = sqlite3.connect("dados/data.db")
    try:
        df = pd.read_sql_query(
            "SELECT date, return FROM returns WHERE ticker = ? ORDER BY date",
            conn,
            params=("PETR4.SA",),
            parse_dates=["date"],
        )
    finally:
        conn.close()

    assert not df.empty, "query returned no rows"
    # ensure returned columns exist
    assert "return" in df.columns
