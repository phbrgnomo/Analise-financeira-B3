import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src import db
from src.db_client import DatabaseClient
from src.ingest.pipeline import ingest_from_snapshot


def make_sample_df(dates, values=None):
    """Helper to craft a simple DataFrame with a date column."""
    if values is None:
        values = list(range(len(dates)))
    return pd.DataFrame({"date": pd.to_datetime(dates), "close": values})


def setup_env(tmp_path, ttl="0", snapshot_dir=None, cache_file=None):
    """Configure environment variables for snapshot tests."""
    if snapshot_dir is None:
        snapshot_dir = tmp_path / "snapshots"
    if cache_file is None:
        cache_file = tmp_path / "snapshot_cache.json"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshot_dir))
    monkeypatch.setenv("SNAPSHOT_TTL", ttl)
    monkeypatch.setenv("SNAPSHOT_CACHE_FILE", str(cache_file))
    monkeypatch.delenv("FORCE_REFRESH", raising=False)
    return monkeypatch, snapshot_dir, cache_file


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

    mp, snap_dir, cache_file = setup_env(tmp_path, ttl="100000")
    caplog.set_level("WARNING")

    # corrupt the cache file so it can't be parsed
    cache_file.write_text("not a json string")

    df = make_sample_df(["2026-01-01"])
    r = ingest_from_snapshot(df, "TEST", db_path=str(db_path))
    assert not r["cached"]
    assert "snapshot cache" in caplog.text.lower()

    mp.undo()


def test_cache_hit_for_unchanged_snapshot(tmp_path, monkeypatch):
    # prepare temporary database
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))

    # set environment with generous TTL so cache is valid
    mp, snap_dir, cache_file = setup_env(tmp_path, ttl="100000")

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
    mp, snap_dir, cache_file = setup_env(tmp_path, ttl="0.001")

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


def test_snapshot_index_created(tmp_path):
    """Recording metadata should create the composite index used by queries.

    We check the sqlite_master table for the expected index name after an
    initial insert. The test doesn't rely on helper functions because the
    operation should work even if the database is otherwise empty.
    """

    db_path = tmp_path / "dados" / "data.db"
    # Schema now managed by migrations; init_db + apply_migrations required
    from src.db_migrator import apply_migrations

    db.init_db(db_path=str(db_path))  # Creates 0000 schema
    conn = db.connect(db_path=str(db_path))
    apply_migrations(conn)  # Applies 0001, 0002
    conn.close()

    metadata = {"ticker": "X", "created_at": "2026-01-01T00:00:00Z"}
    db.record_snapshot_metadata(metadata, db_path=str(db_path))
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND name='snapshots_ticker_created_at_idx'",
    )
    row = cur.fetchone()
    assert row is not None, "index should exist after recording metadata"
    conn.close()


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

    class DummyRepo(DatabaseClient):
        def read_prices(self, *args, **kwargs):
            return existing2

        # other abstract methods are unused in this test and can be
        # satisfied with no-op implementations
        def write_returns(self, df, conn=None, return_type="daily") -> None:
            pass

        def record_snapshot_metadata(self, metadata, conn=None) -> None:
            pass

        def write_prices(
            self, df, ticker, conn=None, db_path=None, source="provider"
        ) -> None:
            pass

    normalized = _normalize_df(df)
    out = _compute_changes(normalized, "T", DummyRepo())
    assert len(out) == 1
    assert out["date"].iloc[0] == pd.Timestamp("2026-01-02")


def test_snapshot_change_triggers_reprocess(tmp_path, monkeypatch):
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))
    mp, snap_dir, cache_file = setup_env(tmp_path, ttl="100000")

    base = make_sample_df(["2026-01-01"])
    ingest_snapshot_and_assert_not_cached(base, db_path)
    # modify the same date value
    changed = make_sample_df(["2026-01-01"], values=[999])
    ingest_snapshot_and_assert_not_cached(changed, db_path)
    mp.undo()


def ingest_snapshot_and_assert_not_cached(snapshot, db_path):
    """Helper for tests: ingest *snapshot* and expect not cached.

    Used by `test_snapshot_change_triggers_reprocess` where successive
    snapshots for the same date are applied.
    """
    r1 = ingest_from_snapshot(snapshot, "FOO", db_path=str(db_path))
    assert not r1["cached"]
    assert r1["rows_processed"] == 1


def test_incremental_ingest_only_new_and_changed_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))
    mp, snap_dir, cache_file = setup_env(tmp_path, ttl="100000")

    ingest_only_new_and_changed_rows_helper(
        date="2026-01-02",
        value=20,
        db_path=db_path,
        expected_rows_processed=2,
    )
    ingest_only_new_and_changed_rows_helper(
        date="2026-01-03",
        value=30,
        db_path=db_path,
        expected_rows_processed=1,
    )
    # verify that the database contains three rows now
    out = db.read_prices("BAR", db_path=str(db_path))
    assert len(out) == 3

    mp.undo()


# helper for incremental ingest tests, called from
# ``test_incremental_ingest_only_new_and_changed_rows``


def ingest_only_new_and_changed_rows_helper(
    date: str,
    value: int,
    db_path,
    expected_rows_processed: int,
):
    """Cria um snapshot com duas datas e ingere, verificando resultados.

    O argumento ``date`` representa a segunda linha do snapshot (a primeira é
    fixa em 2026-01-01). ``value`` é o valor associado à segunda data e
    ``expected_rows_processed`` indica quantas linhas devem ser processadas
    pelo ingest. ``db_path`` é usado para conectar ao banco.
    """
    df1 = make_sample_df(["2026-01-01", date], values=[10, value])
    r1 = ingest_from_snapshot(df1, "BAR", db_path=str(db_path))
    assert not r1["cached"]
    assert r1["rows_processed"] == expected_rows_processed


def test_cache_file_read_fallback_logs_and_metrics(tmp_path, monkeypatch, caplog):
    """If reading the cache file fails we should log a warning and
    increment the metric.
    """
    import src.ingest.snapshot_ingest as sis
    from src import metrics

    db_path = tmp_path / "dados" / "data.db"
    db.init_db(str(db_path))

    mp, snap_dir, cache_file = setup_env(tmp_path, ttl="100000")

    call_count = {"n": 0}
    orig_load = sis.load_cache

    def fake_load_cache(path):
        if call_count["n"] == 0:
            call_count["n"] += 1
            raise OSError("simulated IO failure")
        return orig_load(path)

    monkeypatch.setattr(sis, "load_cache", fake_load_cache)

    caplog.set_level("WARNING")
    called = False

    def fake_inc(name):
        nonlocal called
        if name == "snapshot_cache_fallback":
            called = True

    monkeypatch.setattr(metrics, "increment_counter", fake_inc)

    df = make_sample_df(["2026-01-01"])
    r = ingest_from_snapshot(df, "TEST", db_path=str(db_path))
    assert r["cached"] is False
    assert "snapshot cache" in caplog.text.lower()
    assert called

    mp.undo()


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
        # advance by one day so date-only snapshot filenames change per ingest
        base += timedelta(days=1)
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

    initial_ingest_and_assert_not_cached("2026-01-01", db_path)
    snaps = list((tmp_path / "snaps").glob("RET-*.csv"))
    assert len(snaps) == 1

    initial_ingest_and_assert_not_cached("2026-01-02", db_path)
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


# helper used by test_snapshot_retention_policy to perform an initial
# ingest and assert that it is not cached.
def initial_ingest_and_assert_not_cached(arg0, db_path):
    # first ingestion creates one file
    df1 = make_sample_df([arg0])
    r1 = ingest_from_snapshot(df1, "RET", db_path=str(db_path))
    assert not r1["cached"]


def test_snapshot_checksum_helper():
    """The shared checksum utility should agree with manual serialization.

    This regression test guards against drift between the exporter and the
    ingestion cache logic.  Both sides rely on an identical serialization
    format so the hash values remain stable.
    """
    from src.etl.snapshot import snapshot_checksum
    from src.utils.checksums import serialize_df_bytes, sha256_bytes

    df = make_sample_df(["2026-01-01", "2026-01-02"], values=[1, 2])
    expected_bytes = serialize_df_bytes(
        df,
        index=False,
        date_format="%Y-%m-%d",
        float_format="%.10g",
        na_rep="",
    )
    expected = sha256_bytes(expected_bytes)
    assert snapshot_checksum(df) == expected


def test_ingest_lock_settings(monkeypatch):
    """Lock configuration helper should parse environment variables.

    We verify defaults, a couple of valid permutations, and that invalid
    settings raise ``ValueError`` so callers can treat misconfiguration as a
    hard error.
    """
    from src.ingest.config import get_ingest_lock_settings

    # defaults (no env vars set)
    monkeypatch.delenv("INGEST_LOCK_MODE", raising=False)
    monkeypatch.delenv("INGEST_LOCK_TIMEOUT_SECONDS", raising=False)
    assert get_ingest_lock_settings() == (120.0, "wait", True)

    # explicit timeout and exit mode
    monkeypatch.setenv("INGEST_LOCK_MODE", "exit")
    monkeypatch.setenv("INGEST_LOCK_TIMEOUT_SECONDS", "5")
    assert get_ingest_lock_settings() == (5.0, "exit", False)

    # invalid mode
    monkeypatch.setenv("INGEST_LOCK_MODE", "bogus")
    with pytest.raises(ValueError):
        get_ingest_lock_settings()

    # invalid timeout
    monkeypatch.setenv("INGEST_LOCK_MODE", "wait")
    monkeypatch.setenv("INGEST_LOCK_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(ValueError):
        get_ingest_lock_settings()


def test_snapshot_keep_latest_helper(monkeypatch):
    """The low-level helper parses the env var and enforces a minimum of 1."""
    from src.etl.snapshot import _snapshot_keep_latest
    from src.ingest.config import get_snapshot_keep_latest

    monkeypatch.delenv("SNAPSHOTS_KEEP_LATEST", raising=False)
    assert _snapshot_keep_latest() == 1
    assert get_snapshot_keep_latest() == 1

    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "0")
    assert _snapshot_keep_latest() == 1
    assert get_snapshot_keep_latest() == 1
    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "-5")
    assert _snapshot_keep_latest() == 1
    assert get_snapshot_keep_latest() == 1
    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "3")
    assert _snapshot_keep_latest() == 3
    assert get_snapshot_keep_latest() == 3
    monkeypatch.setenv("SNAPSHOTS_KEEP_LATEST", "abc")
    assert _snapshot_keep_latest() == 1
    assert get_snapshot_keep_latest() == 1
