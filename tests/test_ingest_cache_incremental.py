
import sqlite3

import pandas as pd
import pytest

from src import db
from src.ingest.pipeline import ingest_from_snapshot


def make_sample_df(dates, values=None):
    """Helper to craft a simple DataFrame with a date column."""
    if values is None:
        values = list(range(len(dates)))
    return pd.DataFrame({"date": pd.to_datetime(dates), "close": values})


def setup_env(tmp_path, ttl="0", snapshot_dir=None):
    """Configure environment variables for snapshot tests."""
    if snapshot_dir is None:
        snapshot_dir = tmp_path / "snapshots"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_dir))
    monkeypatch.setenv("SNAPSHOT_TTL", ttl)
    monkeypatch.delenv("FORCE_REFRESH", raising=False)
    return monkeypatch, snapshot_dir



@pytest.mark.parametrize("val", ["1", "true", "True", "yes", " YES "])
def test_env_bool_parsing_true(monkeypatch, val):
    """_env_bool returns True for recognized truthy strings."""
    from src.ingest.pipeline import _env_bool

    monkeypatch.setenv("FLAG", val)
    assert _env_bool("FLAG"), val


@pytest.mark.parametrize("val", ["0", "false", "No", "off", "", "  "])
def test_env_bool_parsing_false(monkeypatch, val):
    """_env_bool returns False for recognized falsy strings."""
    from src.ingest.pipeline import _env_bool

    monkeypatch.setenv("FLAG", val)
    assert not _env_bool("FLAG"), val


@pytest.mark.parametrize("val", ["flase", "maybe", "enable", "yep"])
def test_env_bool_parsing_invalid(monkeypatch, val):
    """_env_bool raises ValueError for unrecognized strings."""
    from src.ingest.pipeline import _env_bool

    monkeypatch.setenv("FLAG", val)
    with pytest.raises(ValueError):
        _env_bool("FLAG")


def test_env_bool_parsing_default(monkeypatch):
    """_env_bool returns False when the variable is unset."""
    from src.ingest.pipeline import _env_bool

    monkeypatch.delenv("FLAG", raising=False)
    assert not _env_bool("FLAG")


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


def test_snapshot_metadata_cache_fallback(tmp_path, monkeypatch, caplog):
    """If reading the metadata file fails initially we should log a warning
    and increment the fallback metric.
    """
    # sourcery skip: no-conditionals-in-tests
    import src.db as _db
    from src import metrics

    # set up a real file so _connect is callable
    db_path = tmp_path / "dados" / "data.db"
    _db.init_db(str(db_path))

    call_count = {"n": 0}
    orig_connect = _db._connect

    def fake_connect(path):
        # fail on first connection (metadata read) but succeed thereafter
        if call_count["n"] == 0:
            call_count["n"] += 1
            raise OSError("simulated IO failure")
        # otherwise delegate to original implementation
        return orig_connect(path)

    monkeypatch.setattr(_db, "_connect", fake_connect)

    caplog.set_level("WARNING")
    called = False

    def fake_inc(name):
        nonlocal called
        if name == "snapshot_metadata_cache_fallback":
            called = True

    monkeypatch.setattr(metrics, "increment_counter", fake_inc)

    df = make_sample_df(["2026-01-01"])
    r = ingest_from_snapshot(df, "TEST", db_path=str(db_path))
    assert r["cached"] is False
    assert "cache fallback" in caplog.text.lower()
    assert called
