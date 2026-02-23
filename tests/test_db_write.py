import os
import sqlite3

import pandas as pd

import src.db as dbmod


def _load_sample_df():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_ticker.csv")
    df = pd.read_csv(path, parse_dates=["date"])  # ticker,date,open,...
    # Keep only price columns and set index
    df = df.set_index("date")
    return df


def test_write_and_read_idempotent():
    conn = sqlite3.connect(":memory:")
    df = _load_sample_df()

    # First write
    dbmod.write_prices(df, "PETR4.SA", conn=conn)
    out = dbmod.read_prices("PETR4.SA", conn=conn)
    assert not out.empty
    first_count = len(out)
    assert first_count == len(df)

    # Second write (idempotent)
    dbmod.write_prices(df, "PETR4.SA", conn=conn)
    out2 = dbmod.read_prices("PETR4.SA", conn=conn)
    assert len(out2) == first_count

    # Check metadata has schema_version
    cur = conn.cursor()
    cur.execute("SELECT value FROM metadata WHERE key='schema_version'")
    row = cur.fetchone()
    # schema_version should match canonical docs/schema.json
    import json
    schema_path = os.path.join(os.path.dirname(__file__), "..", "docs", "schema.json")
    schema_path = os.path.abspath(schema_path)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
            expected = str(schema.get("schema_version", 1))
    except Exception:
        expected = "1"

    assert row is not None and row[0] == expected
