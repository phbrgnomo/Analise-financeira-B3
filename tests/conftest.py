import pytest

from tests.fixture_utils import create_prices_db_from_csv


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
    import os

    env_path = os.environ.get("SNAPSHOT_DIR")
    if env_path:
        os.makedirs(env_path, exist_ok=True)
        return os.path.abspath(env_path)
    d = tmp_path_factory.mktemp("snapshots")
    return str(d)
