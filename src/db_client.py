from __future__ import annotations

import sqlite3
from typing import Optional

import pandas as pd

import src.db as _db


class DatabaseClient:
    """Lightweight DB adapter interface for read/write operations used by core logic."""

    def read_prices(
        self,
        ticker: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> pd.DataFrame:
        raise NotImplementedError()

    def write_returns(
        self, df: pd.DataFrame, conn: Optional[sqlite3.Connection] = None, return_type: str = "daily"
    ) -> None:
        raise NotImplementedError()

    def record_snapshot_metadata(self, metadata: dict, conn: Optional[sqlite3.Connection] = None) -> None:
        raise NotImplementedError()


class DefaultDatabaseClient(DatabaseClient):
    """Default adapter that delegates to `src.db` functional API."""

    def read_prices(self, ticker: str, start: Optional[str] = None, end: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> pd.DataFrame:
        return _db.read_prices(ticker, start=start, end=end, conn=conn)

    def write_returns(self, df: pd.DataFrame, conn: Optional[sqlite3.Connection] = None, return_type: str = "daily") -> None:
        return _db.write_returns(df, conn=conn, return_type=return_type)

    def record_snapshot_metadata(self, metadata: dict, conn: Optional[sqlite3.Connection] = None) -> None:
        return _db.record_snapshot_metadata(metadata, conn=conn)
