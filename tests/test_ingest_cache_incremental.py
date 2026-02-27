
import sqlite3

import pandas as pd
import pytest

from src import db
from src.ingest.pipeline import ingest_from_snapshot


def make_sample_df(dates, values=None):
    """Helper to craft a simple DataFrame with a date column."""
    if values is None:
        values = list(range(len(dates)))
    df = pd.DataFrame({"date": pd.to_datetime(dates), "close": values})
    return df


def setup_env(tmp_path, ttl="0", snapshot_dir=None):
    """Configure environment variables for snapshot tests."""
    if snapshot_dir is None:
        snapshot_dir = tmp_path / "snapshots"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_dir))
    monkeypatch.setenv("SNAPSHOT_TTL", ttl)
    monkeypatch.delenv("FORCE_REFRESH", raising=False)
    return monkeypatch, snapshot_dir


def test_env_bool_parsing(monkeypatch):
    """_env_bool should accept only whitelisted strings and raise on garbage."""
    from src.ingest.pipeline import _env_bool

    monkeypatch.delenv("FLAG", raising=False)
    assert not _env_bool("FLAG")

    true_vals = ["1", "true", "True", "yes", " YES "]
    for val in true_vals:
        monkeypatch.setenv("FLAG", val)
        assert _env_bool("FLAG"), val

    false_vals = ["0", "false", "No", "off", "", "  "]
    for val in false_vals:
        monkeypatch.setenv("FLAG", val)
        assert not _env_bool("FLAG"), val

    for bad in ["flase", "maybe", "enable", "yep"]:
        monkeypatch.setenv("FLAG", bad)
        with pytest.raises(ValueError):
            _env_bool("FLAG")


def test_corrupted_snapshot_metadata_logs(tmp_path, monkeypatch, caplog):
    """If the last snapshot payload is invalid JSON we should warn and
    continue as a cache miss.
    """
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))

    # open DB and insert a row with malformed payload
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        (
            "CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY,"
            " ticker TEXT, created_at TEXT, payload TEXT)"
        )
    )
    cur.execute(
        (
            "INSERT OR REPLACE INTO snapshots (id, ticker, created_at, payload)"
            " VALUES (?, ?, ?, ?)"
        ),
        ("bad", "TEST", "2026-01-01", "not a json string"),
    )
    conn.commit()
    conn.close()

    mp, snap_dir = setup_env(tmp_path, ttl="100000")
    caplog.set_level("WARNING")

    df = make_sample_df(["2026-01-01"])
    r = ingest_from_snapshot(df, "TEST", db_path=str(db_path))
    assert not r["cached"]
    assert "invalid snapshot metadata" in caplog.text.lower()

    mp.undo()


def test_cache_hit_for_unchanged_snapshot(tmp_path, monkeypatch):
    # prepare temporary database
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))

    # set environment with generous TTL so cache is valid
    mp, snap_dir = setup_env(tmp_path, ttl="100000")

    df = make_sample_df(["2026-01-01", "2026-01-02"])

    # first ingestion should write all rows
    r1 = ingest_from_snapshot(df, "TEST", db_path=str(db_path))
    assert not r1["cached"]
    assert r1["rows_processed"] == len(df)
    assert f"{snap_dir}/TEST-" in r1["snapshot_path"]

    # second ingestion with identical df should hit cache
    r2 = ingest_from_snapshot(df, "TEST", db_path=str(db_path))
    assert r2["cached"]
    assert r2["rows_processed"] == 0

    mp.undo()


def test_snapshot_change_triggers_reprocess(tmp_path, monkeypatch):
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))
    mp, snap_dir = setup_env(tmp_path, ttl="100000")

    base = make_sample_df(["2026-01-01"])
    r1 = ingest_from_snapshot(base, "FOO", db_path=str(db_path))
    assert not r1["cached"]
    assert r1["rows_processed"] == 1

    # modify the same date value
    changed = make_sample_df(["2026-01-01"], values=[999])
    r2 = ingest_from_snapshot(changed, "FOO", db_path=str(db_path))
    assert not r2["cached"]
    # because the row existed but was changed, rows_processed should count it
    assert r2["rows_processed"] == 1

    mp.undo()


def test_incremental_ingest_only_new_and_changed_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))
    mp, snap_dir = setup_env(tmp_path, ttl="100000")

    df1 = make_sample_df(["2026-01-01", "2026-01-02"], values=[10, 20])
    r1 = ingest_from_snapshot(df1, "BAR", db_path=str(db_path))
    assert not r1["cached"]
    assert r1["rows_processed"] == 2

    # build a new snapshot with one unchanged row and one new row
    df2 = make_sample_df(["2026-01-01", "2026-01-03"], values=[10, 30])
    r2 = ingest_from_snapshot(df2, "BAR", db_path=str(db_path))
    assert not r2["cached"]
    # only the new row should be processed
    assert r2["rows_processed"] == 1

    # verify that the database contains three rows now
    out = db.read_prices("BAR", db_path=str(db_path))
    assert len(out) == 3

    mp.undo()
