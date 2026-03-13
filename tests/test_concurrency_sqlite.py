import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

import src.db as db_module
from src.db._helpers import _sqlite_version_tuple


@pytest.mark.flaky(reruns=1)
def test_concurrent_writes_file_backed(tmp_path: Path):
    """
    Verifica gravações concorrentes em um banco SQLite file-backed.

    Pré-condição: requer suporte mínimo de SQLite (UPSERT/WAL). Se a versão do
    SQLite for anterior a 3.24.0, o teste é ignorado. O teste escreve linhas
    concorrentes através de múltiplas conexões e valida que ao menos o número
    esperado de linhas foi gravado. Tenta também verificar o `journal_mode`
    (WAL) quando disponível, mas não falha em filesystems onde WAL não é
    suportado.
    """
    # Skip when running against old SQLite versions that lack UPSERT/WAL support
    # sourcery skip: no-conditionals-in-tests
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

    errors = []

    with ThreadPoolExecutor(max_workers=workers) as exe:
        # helper to build a future for worker w
        def make_task(w: int):
            ticker = f"T{w:02d}"

            def task():
                try:
                    # iterate explicitly; we only care about side effects
                    for i in range(rows_per_worker):
                        db_module.write_prices(
                            make_df(
                                start + timedelta(days=w * rows_per_worker + i),
                                n=1,
                            ),
                            ticker,
                            db_path=db_path,
                        )
                except Exception as e:  # pragma: no cover - surface errors
                    return e
                return None

            return exe.submit(task)

        futures = [make_task(w) for w in range(workers)]

        # gather results via comprehension rather than explicit loop
        results = [f.result() for f in as_completed(futures)]
        errors.extend(e for e in results if e)

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

    # Soft-guard: WAL is best-effort. On some filesystems (or SQLite builds)
    # WAL may not be available; mark as xfail rather than hard-failing.
    if not jm.startswith("wal"):
        pytest.xfail(f"journal_mode is {jm!r}; WAL not available on this filesystem")
