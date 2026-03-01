
import sqlite3
import time
from datetime import datetime, timedelta, timezone

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
    """env_bool returns True for recognized truthy strings."""
    from src.ingest.pipeline import env_bool

    monkeypatch.setenv("FLAG", val)
    assert env_bool("FLAG"), val


@pytest.mark.parametrize("val", ["0", "false", "No", "off", "", "  "])
def test_env_bool_parsing_false(monkeypatch, val):
    """env_bool returns False for recognized falsy strings."""
    from src.ingest.pipeline import env_bool

    monkeypatch.setenv("FLAG", val)
    assert not env_bool("FLAG"), val


@pytest.mark.parametrize("val", ["flase", "maybe", "enable", "yep"])
def test_env_bool_parsing_invalid(monkeypatch, val):
    """env_bool raises ValueError for unrecognized strings."""
    from src.ingest.pipeline import env_bool

    monkeypatch.setenv("FLAG", val)
    with pytest.raises(ValueError):
        env_bool("FLAG")


def test_env_bool_parsing_default(monkeypatch):
    """env_bool returns False when the variable is unset."""
    from src.ingest.pipeline import env_bool

    monkeypatch.delenv("FLAG", raising=False)
    assert not env_bool("FLAG")


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


def test_ingest_cache_ttl_expiration(tmp_path, monkeypatch):
    """TTL should expire even if checksum matches.

    We use a very small TTL and sleep briefly to ensure the entry becomes stale.
    """
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))

    # very tiny TTL so it expires quickly
    mp, snap_dir = setup_env(tmp_path, ttl="0.001")

    df = make_sample_df(["2026-01-01", "2026-01-02"], values=[10, 20])

    # first ingest should populate cache
    r1 = ingest_from_snapshot(df, "TTL", db_path=str(db_path))
    assert not r1["cached"]

    # wait longer than TTL
    time.sleep(0.01)

    # same snapshot should no longer be cached
    r2 = ingest_from_snapshot(df, "TTL", db_path=str(db_path))
    assert not r2["cached"]

    mp.undo()
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




def test_shared_diff_helper_and_cli_agree():
    """The extracted helper should produce the same result as the CLI diff."""
    from src.ingest.pipeline import rows_to_ingest
    from src.ingest_cli import _compute_changes, _normalize_df

    # frame with two dates; existing has second row changed
    df = make_sample_df(["2026-01-01", "2026-01-02"], values=[1, 2])
    existing = make_sample_df(["2026-01-01", "2026-01-02"], values=[1, 3])
    # prepare existing as DB would return it
    existing2 = existing.copy()
    existing2["date"] = pd.to_datetime(existing2["date"])
    existing2 = existing2.set_index("date")

    rows = rows_to_ingest(df, existing2)
    assert len(rows) == 1
    assert rows.index[0] == pd.Timestamp("2026-01-02")

    class DummyRepo:
        def read_prices(self, *args, **kwargs):
            return existing2

    normalized = _normalize_df(df)
    out = _compute_changes(normalized, "T", DummyRepo())
    assert len(out) == 1
    assert out["date"].iloc[0] == pd.Timestamp("2026-01-02")


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
    orig_connect = _db.connect

    def fake_connect(path=None):
        # fail on first connection (metadata read) but succeed thereafter
        if call_count["n"] == 0:
            call_count["n"] += 1
            raise OSError("simulated IO failure")
        # otherwise delegate to original implementation
        return orig_connect(path)

    monkeypatch.setattr(_db, "connect", fake_connect)

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


@pytest.fixture
def mock_time_progression(monkeypatch):
    """Fixture that advances the clock by one second on each ``now()`` call.

    Monkeypatches both ``src.ingest.snapshot_ingest.datetime`` and
    ``src.etl.snapshot.datetime`` so that successive invocations of
    ``datetime.now`` produce monotonic, increasing timestamps. This allows
    tests to generate unique snapshot filenames without real ``sleep`` calls.
    """
    base = datetime.now(timezone.utc)

    def _now(tz=None):
        nonlocal base
        base += timedelta(seconds=1)
        return base

    class DummyDatetime:
        @classmethod
        def now(cls, tz=None):
            return _now(tz)

        @classmethod
        def strptime(cls, *args, **kwargs):
            # fallback to real datetime.strptime if needed by snapshot parsing
            return datetime.strptime(*args, **kwargs)

    import importlib

    # patch the actual module objects rather than using string target
    mod1 = importlib.import_module("src.ingest.snapshot_ingest")
    mod2 = importlib.import_module("src.etl.snapshot")
    monkeypatch.setattr(mod1, "datetime", DummyDatetime)
    monkeypatch.setattr(mod2, "datetime", DummyDatetime)



def test_snapshot_retention_policy(monkeypatch, tmp_path, mock_time_progression):
    """Only the most recent N snapshots are retained per ticker.

    The environment variable ``SNAPSHOTS_KEEP_LATEST`` controls how many
    CSV files should be kept; older files (and their checksum siblings)
    should be removed by :func:`ingest_from_snapshot`.
    """
    mp = pytest.MonkeyPatch()
    mp.setenv("SNAPSHOT_DIR", str(tmp_path / "snaps"))
    mp.setenv("SNAPSHOT_TTL", "100000")
    mp.setenv("SNAPSHOTS_KEEP_LATEST", "2")

    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))

    # first ingestion creates one file
    df1 = make_sample_df(["2026-01-01"])
    r1 = ingest_from_snapshot(df1, "RET", db_path=str(db_path))
    assert not r1["cached"]
    snaps = list((tmp_path / "snaps").glob("RET-*.csv"))
    assert len(snaps) == 1

    # second ingestion adds another snapshot; keep=2 should allow both
    df2 = make_sample_df(["2026-01-02"])
    r2 = ingest_from_snapshot(df2, "RET", db_path=str(db_path))
    assert not r2["cached"]
    snaps = sorted((tmp_path / "snaps").glob("RET-*.csv"))
    assert len(snaps) == 2

    # third ingestion triggers retention; only recent two snapshots remain
    df3 = make_sample_df(["2026-01-03"])
    _ = ingest_from_snapshot(df3, "RET", db_path=str(db_path))
    snaps = sorted((tmp_path / "snaps").glob("RET-*.csv"))
    assert len(snaps) == 2

    # os arquivos .checksum associados também devem ser mantidos e corresponder
    remaining_checksums = sorted((tmp_path / "snaps").glob("RET-*.csv.checksum"))
    assert len(remaining_checksums) == 2
    remaining_csv_stems = {p.name for p in snaps}
    remaining_checksum_stems = {
        p.name.replace(".checksum", "") for p in remaining_checksums
    }
    assert remaining_checksum_stems == remaining_csv_stems

    mp.undo()


def test_snapshot_keep_latest_helper(monkeypatch):
    """The low-level helper parses the env var and enforces a minimum of 1.
    """
    from src.etl.snapshot import _snapshot_keep_latest

    monkeypatch.delenv("SNAPSHOTS_KEEP_LATEST", raising=False)
    assert _snapshot_keep_latest() == 1

    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "0")
    assert _snapshot_keep_latest() == 1
    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "-5")
    assert _snapshot_keep_latest() == 1
    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "3")
    assert _snapshot_keep_latest() == 3
    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "abc")
    assert _snapshot_keep_latest() == 1
