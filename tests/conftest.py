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
