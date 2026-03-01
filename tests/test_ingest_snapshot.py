import sqlite3
import time
from pathlib import Path

import pandas as pd
import pytest

from src.ingest_cli import ingest_snapshot
from src.utils.checksums import sha256_file


def _write_snapshot(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)
    checksum = sha256_file(path)
    (path.with_name(path.name + ".checksum")).write_text(checksum)


@pytest.fixture
def empty_db(tmp_path):
    """Creates an in-memory sqlite connection with canonical schema."""
    conn = sqlite3.connect(":memory:")
    # ensure schema exists
    from src.db import _ensure_schema

    _ensure_schema(conn)
    yield conn
    conn.close()


def test_cache_prevents_reprocessing(tmp_path, empty_db):
    # prepare a simple snapshot of two rows
    df = pd.DataFrame(
        {
            "ticker": ["TICK", "TICK"],
            "date": ["2023-01-01", "2023-01-02"],
            "open": [1, 2],
            "high": [1, 2],
            "low": [1, 2],
            "close": [1, 2],
            "volume": [10, 20],
            "source": ["prov", "prov"],
            "fetched_at": ["2023-01-01T00:00:00Z"] * 2,
            "raw_checksum": ["a", "b"],
        }
    )
    snap = tmp_path / "snap.csv"
    _write_snapshot(snap, df)

    cache_file = tmp_path / "cache.json"
    # first ingestion should process both rows
    r1 = ingest_snapshot(
        snap,
        ticker="TICK",
        conn=empty_db,
        cache_file=cache_file,
        ttl=3600,
    )
    assert not r1["cached"]
    assert r1["processed_rows"] == 2
    assert r1["skipped_rows"] == 0

    # second ingestion within TTL should be cached
    r2 = ingest_snapshot(
        snap,
        ticker="TICK",
        conn=empty_db,
        cache_file=cache_file,
        ttl=3600,
    )
    assert r2["cached"]
    assert r2["processed_rows"] == 0


def test_infer_ticker_from_single_entry(tmp_path, empty_db):
    # omit the ticker argument when the snapshot has exactly one ticker
    df = pd.DataFrame(
        {
            "ticker": ["ONE", "ONE"],
            "date": ["2024-01-01", "2024-01-02"],
            "open": [5, 6],
            "high": [5, 6],
            "low": [5, 6],
            "close": [5, 6],
            "volume": [100, 200],
        }
    )
    snap = tmp_path / "infer.csv"
    _write_snapshot(snap, df)

    cache_file = tmp_path / "cache_infer.json"

    # Should work without raising and ingest two rows
    r = ingest_snapshot(snap, conn=empty_db, cache_file=cache_file, ttl=3600)
    assert not r["cached"]
    assert r["processed_rows"] == 2


def test_snapshot_mixed_tickers_raises(tmp_path, empty_db):
    # create a snapshot containing two different tickers
    df = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "date": ["2023-01-01", "2023-01-02"],
            "open": [1, 2],
            "high": [1, 2],
            "low": [1, 2],
            "close": [1, 2],
            "volume": [10, 20],
        }
    )
    snap = tmp_path / "mixed.csv"
    _write_snapshot(snap, df)
    with pytest.raises(ValueError):
        ingest_snapshot(snap, conn=empty_db)


def test_force_refresh_ignores_cache(tmp_path, empty_db):
    df = pd.DataFrame({"ticker": ["TICK"], "date": ["2023-01-01"], "open": [1]})
    snap = tmp_path / "snap2.csv"
    _write_snapshot(snap, df)
    cache_file = tmp_path / "cache2.json"

    ingest_snapshot(snap, ticker="TICK", conn=empty_db, cache_file=cache_file, ttl=3600)
    r = ingest_snapshot(
        snap,
        ticker="TICK",
        conn=empty_db,
        cache_file=cache_file,
        ttl=3600,
        force_refresh=True,
    )
    assert not r["cached"]


def test_ttl_expiration(tmp_path, empty_db):
    df = pd.DataFrame({"ticker": ["TICK"], "date": ["2023-01-01"], "open": [1]})
    snap = tmp_path / "snap3.csv"
    _write_snapshot(snap, df)
    cache_file = tmp_path / "cache3.json"

    ingest_snapshot(snap, ticker="TICK", conn=empty_db, cache_file=cache_file, ttl=1)
    time.sleep(1.1)
    r = ingest_snapshot(
        snap,
        ticker="TICK",
        conn=empty_db,
        cache_file=cache_file,
        ttl=1,
    )
    assert not r["cached"]


def test_incremental_only_new_and_changed(tmp_path, empty_db):
    # initial dataset with two rows
    df1 = pd.DataFrame(
        {
            "ticker": ["TICK", "TICK"],
            "date": ["2023-01-01", "2023-01-02"],
            "open": [1, 2],
            "high": [1, 2],
            "low": [1, 2],
            "close": [1, 2],
            "volume": [10, 20],
            "source": ["prov", "prov"],
            "fetched_at": ["2023-01-01T00:00:00Z"] * 2,
            "raw_checksum": ["x", "y"],
        }
    )
    snap1 = tmp_path / "snap4.csv"
    _write_snapshot(snap1, df1)
    cache_file = tmp_path / "cache4.json"

    # ingest first snapshot
    ingest_snapshot(
        snap1,
        ticker="TICK",
        conn=empty_db,
        cache_file=cache_file,
        ttl=3600,
    )
    # verify DB has two rows
    from src.db import read_prices

    existing = read_prices("TICK", conn=empty_db)
    assert len(existing) == 2

    # build second snapshot: first row unchanged, second row modified, third new
    df2 = pd.DataFrame(
        {
            "ticker": ["TICK", "TICK", "TICK"],
            "date": ["2023-01-01", "2023-01-02", "2023-01-03"],
            "open": [1, 2.5, 3],
            "high": [1, 2.5, 3],
            "low": [1, 2.5, 3],
            "close": [1, 2.5, 3],
            "volume": [10, 25, 30],
            "source": ["prov"] * 3,
            "fetched_at": ["2023-01-01T00:00:00Z"] * 3,
            "raw_checksum": ["x", "z", "w"],
        }
    )
    snap2 = tmp_path / "snap5.csv"
    _write_snapshot(snap2, df2)

    r2 = ingest_snapshot(
        snap2,
        ticker="TICK",
        conn=empty_db,
        cache_file=cache_file,
        ttl=3600,
    )
    # should skip only the first row, process the modified and new one
    assert r2["processed_rows"] == 2
    assert r2["skipped_rows"] == 1
