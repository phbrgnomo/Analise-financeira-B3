import json
import warnings
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

    # passing a non-default db_path should trigger a deprecation warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        meta = save_raw_csv(
            df,
            "testprov",
            "TICK",
            ts,
            raw_root=raw_root,
            metadata_path=metadata_dir / "ingest_logs.jsonl",
            db_path="custom.db",
        )
        assert any(
            isinstance(i.message, DeprecationWarning) for i in w
        ), "expected deprecation warning"

    assert meta["status"] == "success"
    csv_path = Path(meta["filepath"])
    assert csv_path.exists()

    # checksum file
    checksum_path = Path(f"{str(csv_path)}.checksum")
    assert checksum_path.exists()

    # checksum value matches content
    computed = sha256_file(csv_path)
    assert computed == meta["raw_checksum"]
    # metadata JSONL file exists and contains entry
    metadata_path = metadata_dir / "ingest_logs.jsonl"
    assert metadata_path.exists()
    # read JSONL and find entry
    text = metadata_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    entries = [json.loads(line) for line in lines]
    found = [m for m in entries if m.get("job_id") == meta["job_id"]]
    assert len(found) == 1


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
