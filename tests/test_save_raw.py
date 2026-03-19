import json
import sqlite3
import warnings
from pathlib import Path

import pandas as pd
import pytest

from src.ingest.pipeline import save_raw_csv
from src.utils.checksums import sha256_file


def test_save_raw_csv_and_register(tmp_path):
    """Ensure save_raw_csv writes CSV/metadata and warns when custom db_path is used.

    This verifies that `save_raw_csv()` successfully writes a raw CSV and
    associated metadata entry, and emits a deprecation warning when a
    non-default `db_path` is passed.
    """

    df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

    raw_root = tmp_path / "raw"
    ts = "20260220T000000Z"

    # use default metadata file under tmp_path/metadata by patching cwd via raw_root
    metadata_dir = tmp_path / "metadata"

    # Ensure the warning is emitted even if a previous test already triggered
    # the global suppression flag. Use the module-provided test helper rather
    # than mutating private state directly.
    import src.ingest.raw_storage as raw_storage  # noqa: F401

    raw_storage._test_reset_deprecation_warning()

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
        # ensure we got a deprecation warning and that the warning points to
        # the caller (this test file) rather than raw_storage itself.
        assert any(isinstance(i.message, DeprecationWarning) for i in w), (
            "expected deprecation warning"
        )
        last = w[-1]
        # filename should not mention raw_storage; it should refer to this test
        assert "raw_storage.py" not in last.filename
        assert last.filename.endswith("test_save_raw.py"), (
            "warning should reference the user's call site"
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
    # metadata JSONL file exists and contains entry
    metadata_path = metadata_dir / "ingest_logs.jsonl"
    assert metadata_path.exists()
    # read JSONL and find entry
    text = metadata_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    entries = [json.loads(line) for line in lines]
    found = [m for m in entries if m.get("job_id") == meta["job_id"]]
    assert len(found) == 1


def assert_ingest_log_entry(conn: sqlite3.Connection, meta: dict[str, object]) -> None:
    """Assert that the given metadata record exists in the ingest log.

    Parameters
    ----------
    conn : sqlite3.Connection
        A connection to the metadata database.
    meta : dict[str, object]
        Metadata dict produced by `save_raw_csv`, expected to include at least
        ``job_id`` and ``filepath``.

    Raises
    ------
    AssertionError
        If the ingest log entry is missing or does not match the expected values.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT job_id, status, filepath FROM ingest_logs WHERE job_id = ?",
        (meta["job_id"],),
    )
    row = cur.fetchone()
    assert row is not None
    assert row[1] == "success"
    assert row[2] == meta["filepath"]


def test_timestamp_validation():
    """Verify _resolve_timestamp_str enforces timezone-awareness and format."""
    from datetime import datetime, timezone

    from src.ingest.raw_storage import _resolve_timestamp_str

    # None returns a UTC timestamp string
    out = _resolve_timestamp_str(None)
    assert out.endswith("Z") and len(out) == 16

    # aware datetime is converted correctly
    aware = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert _resolve_timestamp_str(aware) == "20260101T000000Z"

    # naive datetime should raise
    naive = datetime(2026, 1, 1, 0, 0, 0)
    with pytest.raises(ValueError):
        _resolve_timestamp_str(naive)

    # valid string passes unchanged
    assert _resolve_timestamp_str("20260101T123456Z") == "20260101T123456Z"

    # invalid strings raise
    with pytest.raises(ValueError):
        _resolve_timestamp_str("2026-01-01T00:00:00Z")
    with pytest.raises(ValueError):
        _resolve_timestamp_str("not-a-timestamp")
