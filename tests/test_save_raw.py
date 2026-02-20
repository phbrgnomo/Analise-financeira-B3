import sqlite3
from pathlib import Path

import pandas as pd

from src.ingest.pipeline import save_raw_csv
from src.utils.checksums import sha256_file


def test_save_raw_csv_and_register(tmp_path):
    df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

    raw_root = tmp_path / "raw"
    db_path = tmp_path / "data.db"

    ts = "20260220T000000Z"

    meta = save_raw_csv(df, "testprov", "TICK", ts, raw_root=raw_root, db_path=db_path)

    assert meta["status"] == "success"
    csv_path = Path(meta["filepath"])
    assert csv_path.exists()

    # checksum file
    checksum_path = Path(str(csv_path) + ".checksum")
    assert checksum_path.exists()

    # checksum value matches content
    computed = sha256_file(csv_path)
    assert computed == meta["raw_checksum"]

    # DB entry exists
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT job_id, status, filepath FROM ingest_logs WHERE job_id = ?",
            (meta["job_id"],),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[1] == "success"
        assert row[2] == meta["filepath"]
    finally:
        conn.close()
