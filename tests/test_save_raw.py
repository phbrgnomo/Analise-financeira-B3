import json
from pathlib import Path

import pandas as pd

from src.ingest.pipeline import save_raw_csv
from src.utils.checksums import sha256_file


def test_save_raw_csv_and_register(tmp_path):
    df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

    raw_root = tmp_path / "raw"
    ts = "20260220T000000Z"

    # use default metadata file under tmp_path/metadata by patching cwd via raw_root
    metadata_dir = tmp_path / "metadata"

    meta = save_raw_csv(
        df,
        "testprov",
        "TICK",
        ts,
        raw_root=raw_root,
        metadata_path=metadata_dir / "ingest_logs.json",
    )

    assert meta["status"] == "success"
    csv_path = Path(meta["filepath"])
    assert csv_path.exists()

    # checksum file
    checksum_path = Path(f"{str(csv_path)}.checksum")
    assert checksum_path.exists()

    # checksum value matches content
    computed = sha256_file(csv_path)
    assert computed == meta["raw_checksum"]
    # metadata JSON file exists and contains entry
    metadata_path = metadata_dir / "ingest_logs.json"
    assert metadata_path.exists()
    content = json.loads(metadata_path.read_text())
    found = [m for m in content if m.get("job_id") == meta["job_id"]]
    assert len(found) == 1


# TODO Rename this here and in `test_save_raw_csv_and_register`
def assert_ingest_log_entry(conn, meta):
    cur = conn.cursor()
    cur.execute(
        "SELECT job_id, status, filepath FROM ingest_logs WHERE job_id = ?",
        (meta["job_id"],),
    )
    row = cur.fetchone()
    assert row is not None
    assert row[1] == "success"
    assert row[2] == meta["filepath"]
