import sqlite3

from src import db as src_db


def test_init_ingest_db_creates_expected_metadata_table(tmp_path):
    db_file = tmp_path / "dados" / "data.db"
    # Create the DB file and schema via src.db helper
    src_db.create_tables_if_not_exists(db_path=str(db_file))

    # Inspect the created schema
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info('metadata');")
    rows = cur.fetchall()
    conn.close()

    # Expect metadata table with columns key and value
    col_names = [r[1] for r in rows]
    assert "key" in col_names
    assert "value" in col_names
