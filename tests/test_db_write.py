import pandas as pd
import sqlalchemy
import pytest

from src import db


@pytest.fixture
def engine():
    # in-memory SQLite engine for isolation
    return sqlalchemy.create_engine("sqlite+pysqlite:///:memory:", future=True)


def sample_df():
    return pd.DataFrame({
        "date": pd.to_datetime(["2021-01-01", "2021-01-02"]),
        "open": [10.0, 11.0],
        "high": [10.5, 11.5],
        "low": [9.5, 10.5],
        "close": [10.2, 11.2],
        "volume": [1000, 1100],
        "source": ["yfinance", "yfinance"],
    })


def test_write_and_read(engine):
    df = sample_df()
    # prepare schema
    db.create_tables_if_not_exists(engine)
    db.write_prices(df, ticker="TEST", engine=engine)
    out = db.read_prices("TEST", engine=engine)
    assert len(out) == 2
    assert "close" in out.columns


def test_upsert_idempotent(engine):
    df = sample_df()
    db.create_tables_if_not_exists(engine)
    db.write_prices(df, "TEST", engine=engine)
    # update second row and write again
    df2 = df.copy()
    df2.loc[1, "close"] = 99.9
    db.write_prices(df2, "TEST", engine=engine)
    out = db.read_prices("TEST", engine=engine)
    assert len(out) == 2
    assert any(out["close"] == 99.9)


def test_schema_version_written(engine):
    df = sample_df()
    db.create_tables_if_not_exists(engine)
    db.write_prices(df, "TEST", engine=engine, schema_version="1.0")

    with engine.connect() as conn:
        res = conn.execute(sqlalchemy.select(db.metadata_table.c.value).where(db.metadata_table.c.key == 'schema_version'))
        val = res.scalar()

    assert val == "1.0"
