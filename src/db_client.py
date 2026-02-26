from __future__ import annotations

import abc
import sqlite3
from typing import Any, Dict, Optional

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
        db_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """Read price rows for a ticker from the persistence layer.

        Parameters
        ----------
        ticker:
            Ticker identifier (e.g. "PETR4.SA").
        start, end:
            Optional date bounds (``YYYY-MM-DD``) to filter rows.
        conn:
            Optional ``sqlite3.Connection`` instance to use. When provided,
            the implementation should use this connection and not open a new
            one.
        db_path:
            Optional filesystem path / URI for the SQLite database. When
            provided and ``conn`` is None, implementations may open a
            connection to this path. If the adapter manages connections
            centrally, this parameter can be ignored — document such
            behavior in the concrete implementation.

        Returns
        -------
        pandas.DataFrame
            DataFrame indexed by date with the columns defined by the
            canonical schema. When no rows match, return an empty DataFrame.
        """

    @abc.abstractmethod
    def write_returns(
        self,
        df: pd.DataFrame,
        conn: Optional[sqlite3.Connection] = None,
        return_type: str = "daily",
    ) -> None:
        pass

    @abc.abstractmethod
    def record_snapshot_metadata(
        self,
        metadata: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
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

    def read_prices(
        self,
        ticker: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
        db_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """Adapter wrapper around `src.db.read_prices`.

        This default implementation delegates to the functional API in
        `src.db`. It accepts an optional ``conn`` and optional ``db_path``;
        when ``conn`` is omitted and ``db_path`` is provided, the underlying
        `src.db.read_prices` will open a connection to that path.
        """
        return _db.read_prices(
            ticker,
            start=start,
            end=end,
            conn=conn,
            db_path=db_path,
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
