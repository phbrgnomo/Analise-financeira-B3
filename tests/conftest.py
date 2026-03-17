"""Conftest de testes global.

Define fixtures úteis para integração e playback de rede.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import types
from datetime import datetime, timedelta, timezone
from typing import Callable, Generator

import pandas as pd
import pytest

from src import db
from src.adapters.retry_metrics import get_global_metrics
from src.db_migrator import apply_migrations
from src.utils.checksums import sha256_file

# Ensure tests directory is importable when pytest runs the tests as a script
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from fixture_utils import create_prices_db_from_csv, get_or_make_snapshot_dir


def _load_sample_dataframe(ticker: str, start=None, end=None, **kwargs) -> pd.DataFrame:
    path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_ticker.csv")
    # CSV possui cabeçalho: usar nomes originais e converter 'date' para datetime
    df = pd.read_csv(path, parse_dates=["date"])  # uses header=0 by default
    df = df.set_index("date")
    # Garantir que o índice é DatetimeIndex
    df.index = pd.to_datetime(df.index, utc=False)

    # Normalizar nomes de colunas para formato esperado pelo adapter (provider style)
    col_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df = df.rename(columns=col_map)

    # Garantir colunas esperadas do provedor: Open, High, Low, Close, Volume
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = None

    # Não expor "Adj Close" nos dados de playback: DB não contém essa coluna.
    return df[["Open", "High", "Low", "Close", "Volume"]]


@pytest.fixture(autouse=True)
def reset_retry_metrics():
    """Reset the global retry-metrics singleton before every test.

    Prevents retry counters from leaking between tests when the same process
    runs the full suite, which could produce non-deterministic assertions in
    tests that inspect retry/failure counts.
    """
    get_global_metrics().reset()
    yield
    # reset again after the test so any metric mutations don't bleed into
    # fixtures that run during teardown.
    get_global_metrics().reset()


@pytest.fixture(autouse=True)
def mock_yfinance_data(monkeypatch) -> Generator[Callable, None, None]:
    """Monkeypatch `src.adapters.yfinance_adapter.web.DataReader` para playback.

    Usa `tests/fixtures/sample_ticker.csv` como fonte determinística quando
    `NETWORK_MODE!=record`.
    """
    mode = os.environ.get("NETWORK_MODE", "playback").lower()
    if mode == "record":
        yield lambda *a, **k: None
        return

    def _patched_datareader(ticker, data_source=None, start=None, end=None, **kwargs):
        return _load_sample_dataframe(ticker, start=start, end=end, **kwargs)

    import src.adapters.yfinance_adapter as yadapter  # type: ignore

    ns = yadapter.types.SimpleNamespace(DataReader=_patched_datareader)
    monkeypatch.setattr(yadapter, "web", ns)
    yield _patched_datareader


@pytest.fixture
def yfinance_stub(monkeypatch):
    """Stub out the `yfinance` module used by `YFinanceAdapter.test_connection`.

    This fixture emulates the situation where `yfinance` is not installed
    and the adapter should report unavailable.
    """
    import src.adapters.yfinance_adapter as yfa  # type: ignore

    ns = types.SimpleNamespace(__is_stub__=True)
    monkeypatch.setattr(yfa, "yf", ns)
    yield ns


@pytest.fixture
def yfinance_present(monkeypatch):
    """Provide a minimal yfinance stub with the API surface expected by the adapter.

    Used by tests that need `YFinanceAdapter.test_connection()` to return True.
    """
    import src.adapters.yfinance_adapter as yfa  # type: ignore

    ns = types.SimpleNamespace(
        download=lambda *a, **k: None,
        Ticker=lambda *a, **k: None,
        __is_stub__=False,
    )
    monkeypatch.setattr(yfa, "yf", ns)
    yield ns


@pytest.fixture
def fake_ingest_success(monkeypatch):
    """Fixture that stubs src.ingest.pipeline.ingest to return a successful result."""

    def _fake_ingest(*args, **kwargs):
        return {
            "status": "success",
            "persist": {
                "rows_processed": 1,
                "snapshot_path": "snapshots/PETR4-20260215.csv",
                "checksum": "abc",
            },
        }

    monkeypatch.setattr("src.ingest.pipeline.ingest", _fake_ingest)
    return _fake_ingest


@pytest.fixture
def fake_ingest_failure(monkeypatch):
    """Fixture that stubs src.ingest.pipeline.ingest to return a failure result."""

    def _fake_ingest(*args, **kwargs):
        return {"status": "failure", "error_message": "boom: ingest failed"}

    monkeypatch.setattr("src.ingest.pipeline.ingest", _fake_ingest)
    return _fake_ingest


@pytest.fixture
def fake_compute_rows1(monkeypatch):
    """Fixture that stubs src.main._compute_returns_for_ticker to return 1 row."""

    def _fake_compute(*args, **kwargs):
        return {"rows": 1, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", _fake_compute)
    return _fake_compute


@pytest.fixture
def fake_compute_rows0(monkeypatch):
    """Fixture that stubs src.main._compute_returns_for_ticker to return 0 rows."""

    def _fake_compute(*args, **kwargs):
        return {"rows": 0, "persisted": False, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", _fake_compute)
    return _fake_compute


@pytest.fixture(scope="function")
def sample_db():
    """Creates an in-memory SQLite DB seeded with tests/fixtures/sample_ticker.csv

    Yields a `sqlite3.Connection` object that tests can use.
    """
    db = create_prices_db_from_csv("sample_ticker.csv")

    try:
        yield db
    finally:
        # Ensure the connection is always closed after each test
        db.close()


@pytest.fixture(autouse=True)
def sqlite_version_override(monkeypatch):
    """If `SQLITE_VERSION` env var is set in CI, monkeypatch sqlite3.sqlite_version.

    This allows CI to simulate different SQLite runtime versions without
    recompiling Python. The test suite uses this to exercise upsert vs
    fallback code paths deterministically.
    """

    if ver := os.environ.get("SQLITE_VERSION"):
        monkeypatch.setattr(sqlite3, "sqlite_version", ver)
    yield


@pytest.fixture
def mock_metadata_db(tmp_path, monkeypatch):
    """Prepare a metadata database and patch ``db.connect`` to point at it.

    Yields
    ------
    tuple[sqlite3.Connection, pathlib.Path]
        The open connection and the path to the metadata DB.  The connection
        is closed after the test automatically.
    """
    metadata_db_path = tmp_path / "metadata.db"
    # initialize and migrate a fresh metadata database
    db.init_db(db_path=str(metadata_db_path))
    metadata_conn = db.connect(db_path=str(metadata_db_path))
    apply_migrations(metadata_conn)

    original_connect = db.connect

    def mock_db_connect(db_path=None, **kw):
        # ignore any requested path, always return connection to our test DB
        return original_connect(db_path=str(metadata_db_path), **kw)

    monkeypatch.setattr(db, "connect", mock_db_connect)

    try:
        yield metadata_conn, metadata_db_path
    finally:
        metadata_conn.close()


@pytest.fixture
def purge_test_setup(tmp_path, monkeypatch):
    """Prepare a metadata DB with one old snapshot and return paths.

    This mirrors the setup previously duplicated across multiple retention
    purge tests.  The returned tuple contains:

    * ``test_csv``: Path to the created snapshot CSV file
    * ``metadata_db_path``: Path to the temporary metadata database file
    * ``checksum``: SHA-256 checksum of the created snapshot CSV (used in
      assertions that metadata matches the file contents)

    The fixture also monkeypatches :func:`src.db.connect` so that calls from
    the CLI under test will always use this database.
    """
    metadata_db_path = tmp_path / "metadata.db"
    db.init_db(db_path=str(metadata_db_path))
    metadata_conn = db.connect(db_path=str(metadata_db_path))
    apply_migrations(metadata_conn)

    # create CSV and checksum
    test_csv = tmp_path / "PETR4_snapshot.csv"
    df = pd.DataFrame(
        {
            "date": ["2023-01-01"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000],
            "ticker": ["PETR4"],
        }
    )
    df.to_csv(test_csv, index=False)
    checksum = sha256_file(test_csv)

    old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    cur = metadata_conn.cursor()
    cur.execute(
        "INSERT INTO snapshots (id, ticker, snapshot_path, checksum, "
        "size_bytes, created_at, archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "1",
            "PETR4",
            str(test_csv),
            checksum,
            test_csv.stat().st_size,
            old_date,
            0,
        ),
    )
    metadata_conn.commit()
    metadata_conn.close()

    original_connect = db.connect

    def patched_connect(db_path=None, **kw):
        return original_connect(db_path=str(metadata_db_path), **kw)

    monkeypatch.setattr(db, "connect", patched_connect)

    return test_csv, metadata_db_path, checksum


@pytest.fixture(autouse=True)
def isolate_metadata_db(tmp_path, monkeypatch):
    """Autouse fixture que garante que cada teste use um DB de metadata isolado.

    Alguns testes podem esquecer de monkeypatchar conexões; esta fixture
    força `db.connect` e o conector interno `src.db.connection._connect` a
    retornarem uma conexão para um banco temporário por teste.
    """
    metadata_db_path = tmp_path / "metadata_isolated.db"
    # create and migrate a fresh metadata database file (use real connect)
    # Use the low-level connector so we can redirect all calls (including
    # ones that import `db.connect` at import-time) to the isolated metadata DB.
    from src.db import connection

    orig_connect = connection._connect
    # initialize DB file and apply migrations
    conn_tmp = orig_connect(db_path=str(metadata_db_path))
    try:
        apply_migrations(conn_tmp)
    finally:
        conn_tmp.close()

    def _test_connect(db_path=None, **kw):
        # Redirect default (None) connections to our isolated metadata DB;
        # explicit db_path requests are forwarded unchanged so tests that
        # create their own DB files still work.
        if db_path is None:
            return orig_connect(db_path=str(metadata_db_path), **kw)
        return orig_connect(db_path=db_path, **kw)

    monkeypatch.setattr(connection, "_connect", _test_connect)

    # nothing to close here; connect() returns fresh connections per call
    yield


@pytest.fixture(scope="function")
def sample_db_multi():
    """Creates an in-memory SQLite DB seeded with tests/fixtures/sample_ticker_multi.csv

    Yields a `sqlite3.Connection` object that tests can use.
    """
    db = create_prices_db_from_csv("sample_ticker_multi.csv")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def snapshot_dir(tmp_path_factory) -> str:
    """Diretório temporário (ou `SNAPSHOT_DIR` quando definido) para salvar
    snapshots gerados nos testes.

    Se a variável de ambiente `SNAPSHOT_DIR` estiver definida (ex.: em CI), usamos
    esse caminho e garantimos que ele exista; caso contrário, criamos um
    diretório temporário isolado.
    """

    env_path = os.environ.get("SNAPSHOT_DIR")
    return get_or_make_snapshot_dir(env_path, tmp_path_factory)
