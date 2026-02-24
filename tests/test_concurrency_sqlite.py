import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import pytest

import src.db as db_module


def _sqlite_version_tuple():
    parts = []
    for p in sqlite3.sqlite_version.split("."):
        numeric = ""
        for ch in p:
            if ch.isdigit():
                numeric += ch
            else:
                break
        if not numeric:
            break
        parts.append(int(numeric))
    return tuple(parts)


@pytest.mark.flaky(reruns=1)
def test_concurrent_writes_file_backed(tmp_path):
    # Skip when running against old SQLite versions that lack UPSERT/WAL support
    if _sqlite_version_tuple() < (3, 24, 0):
        pytest.skip("SQLite too old for concurrency test; skipping")

    db_file = tmp_path / "data.db"
    db_path = str(db_file)

    # Ensure DB and schema exist
    db_module.init_db(db_path)

    # Build small DataFrame generator
    def make_df(start_date: datetime, n: int = 5):
        dates = [start_date + timedelta(days=i) for i in range(n)]
        df = pd.DataFrame(
            {
                "date": dates,
                "open": [1.0] * n,
                "high": [1.0] * n,
                "low": [1.0] * n,
                "close": [1.0] * n,
                "volume": [100] * n,
            }
        )
        return df

    workers = 8
    rows_per_worker = 20

    start = datetime(2020, 1, 1)

    futures = []
    errors = []

    with ThreadPoolExecutor(max_workers=workers) as exe:
        for w in range(workers):
            # each worker will write rows_per_worker different dates for its ticker
            ticker = f"T{w:02d}"

            def task(t=ticker, offset=w):
                try:
                    for i in range(rows_per_worker):
                        day = start + timedelta(days=offset * rows_per_worker + i)
                        df = make_df(day, n=1)
                        # write_prices will open its own connection (as designed)
                        db_module.write_prices(df, t, db_path=db_path)
                except Exception as e:  # pragma: no cover - surface errors
                    return e
                return None

            futures.append(exe.submit(task))

        for f in as_completed(futures):
            exc = f.result()
            if exc:
                errors.append(exc)

    assert not errors, f"Worker errors occurred: {errors}"

    # Verify total rows written
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        total = cur.fetchone()[0]
    finally:
        conn.close()

    expected = workers * rows_per_worker
    assert total >= expected, f"Expected at least {expected} rows, found {total}"

    # Check journal_mode (best-effort): should be wal when supported
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode;")
        jm = cur.fetchone()[0]
    finally:
        conn.close()

    assert jm.startswith("wal") or jm == "wal", f"Unexpected journal_mode: {jm}"
