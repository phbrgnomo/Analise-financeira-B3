"""Módulo de persistência simples para story 1.6.

Fornece funções:
- create_tables_if_not_exists(engine=None)
- write_prices(df, ticker, engine=None, schema_version=None)
- read_prices(ticker, start=None, end=None, engine=None)

Implementação usa SQLAlchemy Core e upsert (`ON CONFLICT`) no SQLite.
"""

import datetime
import sqlite3
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# Metadados e tabelas (definidos no nível do módulo para facilitar testes)
metadata = MetaData()

prices = Table(
    "prices",
    metadata,
    Column("ticker", String, primary_key=True),
    Column("date", Date, primary_key=True),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("volume", Integer),
    Column("source", String),
    Column("fetched_at", DateTime),
    Column("raw_checksum", String),
)

metadata_table = Table(
    "metadata",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", String),
)

# Expose table objects with stable names expected in tests
prices_table = prices


def _sqlite_runtime_version(engine=None):
    """Return SQLite runtime version as a tuple, e.g. (3, 39, 2).

    This helper is overridable in tests via monkeypatch to simulate different
    SQLite runtime capabilities.
    """
    try:
        v = sqlite3.sqlite_version_info
        return v
    except Exception:
        return (0, 0, 0)


def _get_engine(engine=None, db_path: Optional[str] = None):
    if engine is not None:
        return engine
    if db_path is None:
        db_path = "dados/data.db"
    url = f"sqlite:///{db_path}"
    return create_engine(url, future=True)


def create_tables_if_not_exists(engine=None, db_path: Optional[str] = None):
    """Cria as tabelas necessárias se não existirem."""
    # Garantir que o diretório do banco exista para evitar erro do SQLite
    if db_path is None:
        db_path = "dados/data.db"
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    eng = _get_engine(engine, db_path)
    metadata.create_all(eng)


def write_prices(
    df,
    ticker: str,
    engine=None,
    schema_version: Optional[str] = None,
    db_path: Optional[str] = None,
):
    """Grava ou atualiza (upsert) linhas da tabela `prices` por (ticker, date).

    Parâmetros de apoio usados especialmente em testes:
    - engine: SQLAlchemy Engine (opcional)
    - schema_version: valor para gravar/atualizar em metadata.key == 'schema_version'
    """
    import hashlib

    import pandas as pd

    eng = _get_engine(engine, db_path)

    # Normalizar DataFrame
    if "date" not in df.columns:
        df = df.reset_index()

    rows = []
    for _, row in df.iterrows():
        date_val = pd.to_datetime(row["date"]).date()
        fetched_at_val = row.get("fetched_at", datetime.datetime.utcnow())
        # construir checksum determinístico simples a partir das colunas de interesse
        raw_payload = "|".join(
            [
                str(row.get("date", "")),
                str(row.get("open", "")),
                str(row.get("high", "")),
                str(row.get("low", "")),
                str(row.get("close", "")),
                str(row.get("volume", "")),
                str(row.get("source", "")),
            ]
        )
        raw_checksum = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

        row_dict = {
            "ticker": ticker,
            "date": date_val,
            "open": float(row.get("open")) if pd.notna(row.get("open")) else None,
            "high": float(row.get("high")) if pd.notna(row.get("high")) else None,
            "low": float(row.get("low")) if pd.notna(row.get("low")) else None,
            "close": float(row.get("close")) if pd.notna(row.get("close")) else None,
            "volume": int(row.get("volume")) if pd.notna(row.get("volume")) else None,
            "source": row.get("source"),
            "fetched_at": pd.to_datetime(fetched_at_val),
            "raw_checksum": raw_checksum,
        }
        rows.append(row_dict)

    if not rows:
        return

    stmt = sqlite_insert(prices_table)
    # construir mapping de atualização para todas as colunas exceto PKs
    update_cols = {
        col.name: getattr(stmt.excluded, col.name)
        for col in prices_table.c
        if col.name not in ("ticker", "date")
    }

    # Use optimized ON CONFLICT ... WHERE when the runtime SQLite supports it.
    sqlite_ver = _sqlite_runtime_version(eng)
    if sqlite_ver >= (3, 24, 0):
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_=update_cols,
            where=(prices_table.c.raw_checksum != stmt.excluded.raw_checksum),
        )

        with eng.begin() as conn:
            conn.execute(upsert_stmt, rows)

            if schema_version is not None:
                # grava/atualiza schema_version na tabela metadata
                m_stmt = sqlite_insert(metadata_table).values(
                    key="schema_version", value=schema_version
                )
                m_upsert = m_stmt.on_conflict_do_update(
                    index_elements=["key"], set_={"value": m_stmt.excluded.value}
                )
                conn.execute(m_upsert)
    else:
        # Fallback for older SQLite: perform per-row check to avoid overwriting
        # rows when raw_checksum is unchanged (preserve fetched_at).
        with eng.begin() as conn:
            for r in rows:
                sel = select(prices_table.c.raw_checksum).where(
                    (prices_table.c.ticker == r["ticker"])
                    & (prices_table.c.date == r["date"])
                )
                existing = conn.execute(sel).scalar()
                if existing is None:
                    conn.execute(prices_table.insert().values(**r))
                else:
                    if existing == r.get("raw_checksum"):
                        # identical payload, skip update
                        continue
                    # perform update of non-PK columns
                    upd_vals = {k: r[k] for k in update_cols.keys()}
                    upd = (
                        prices_table.update()
                        .where(
                            (prices_table.c.ticker == r["ticker"])
                            & (prices_table.c.date == r["date"])
                        )
                        .values(**upd_vals)
                    )
                    conn.execute(upd)

            if schema_version is not None:
                m_stmt = sqlite_insert(metadata_table).values(
                    key="schema_version", value=schema_version
                )
                m_upsert = m_stmt.on_conflict_do_update(
                    index_elements=["key"], set_={"value": m_stmt.excluded.value}
                )
                conn.execute(m_upsert)


def read_prices(
    ticker: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    engine=None,
    db_path: Optional[str] = None,
):
    """Lê preços por ticker e intervalo opcional (start, end).

    Retorna um pandas.DataFrame.
    """
    import pandas as pd

    eng = _get_engine(engine, db_path)
    sel = select(prices_table).where(prices_table.c.ticker == ticker)

    if start is not None:
        sel = sel.where(prices_table.c.date >= pd.to_datetime(start).date())
    if end is not None:
        sel = sel.where(prices_table.c.date <= pd.to_datetime(end).date())

    sel = sel.order_by(prices_table.c.date)

    with eng.connect() as conn:
        res = conn.execute(sel)
        rows = res.fetchall()

    if not rows:
        return pd.DataFrame(columns=[c.name for c in prices_table.c])

    df = pd.DataFrame([dict(row._mapping) for row in rows])
    return df
