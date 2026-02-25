from __future__ import annotations

import sqlite3
import abc
from typing import Optional, Dict, Any

import pandas as pd

import src.db as _db


class DatabaseClient(abc.ABC):
    """Lightweight DB adapter interface for read/write operations used by core logic."""

    @abc.abstractmethod
    def read_prices(
        self,
        ticker: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> pd.DataFrame:
        pass

    @abc.abstractmethod
    def write_returns(
        self, df: pd.DataFrame, conn: Optional[sqlite3.Connection] = None, return_type: str = "daily"
    ) -> None:
        pass

    @abc.abstractmethod
    def record_snapshot_metadata(self, metadata: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> None:
        pass

    @abc.abstractmethod
    def write_prices(
        self,
        df: pd.DataFrame,
        ticker: str,
        conn: Optional[sqlite3.Connection] = None,
        db_path: Optional[str] = None,
        source: str = "provider",
    ) -> None:
        pass


class DefaultDatabaseClient(DatabaseClient):
    """Default adapter that delegates to `src.db` functional API."""

    def read_prices(self, ticker: str, start: Optional[str] = None, end: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> pd.DataFrame:
        return _db.read_prices(
            ticker,
            start=start,
            end=end,
            conn=conn,
        )

    def write_returns(
        self,
        df: pd.DataFrame,
        conn: Optional[sqlite3.Connection] = None,
        return_type: str = "daily",
    ) -> None:
        return _db.write_returns(
            df,
            conn=conn,
            return_type=return_type,
        )

    def write_prices(
        self,
        df: pd.DataFrame,
        ticker: str,
        conn: Optional[sqlite3.Connection] = None,
        db_path: Optional[str] = None,
        source: str = "provider",
    ) -> None:
        return _db.write_prices(
            df,
            ticker,
            conn=conn,
            db_path=db_path,
            source=source,
        )

    def record_snapshot_metadata(
        self,
        metadata: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        return _db.record_snapshot_metadata(
            metadata,
            conn=conn,
        )
