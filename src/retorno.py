"""Cálculo e persistência de retornos financeiros de ativos da B3.

Expõe :func:`compute_returns` como principal ponto de entrada, que lê preços
do banco SQLite, calcula log-retornos e salva o resultado em CSV.  Funções
auxiliares de conversão de retorno/risco (:func:`r_linear`, :func:`r_log`,
:func:`retorno_periodo`, :func:`conv_retorno`, :func:`conv_risco`,
:func:`coef_var`, :func:`correlacao`) também estão disponíveis.
"""

import contextlib
import logging
import math
import sqlite3
import time
import uuid
from datetime import date, datetime
from typing import Optional, Tuple, Union

import numpy as np
import pandas as pd

import src.db as _db
from src import metrics  # noqa: E402
from src.db_client import DatabaseClient, DefaultDatabaseClient
from src.paths import DATA_DIR
from src.time_utils import now_utc_iso

logger = logging.getLogger(__name__)

# Convenção de dias de negociação para anualização
TRADING_DAYS = 252


def compute_returns(
    ticker: str,
    start: str | date | datetime | None = None,
    end: str | date | datetime | None = None,
    repo: Optional[DatabaseClient] = None,
    conn: sqlite3.Connection | None = None,
    dry_run: bool = False,
) -> pd.DataFrame | None:
    """Compute simple daily returns for `ticker` and persist to `returns` table.

    - Reads `prices` from provided ``repo`` adapter.  When ``repo`` is None a
      :class:`DefaultDatabaseClient` is created automatically.
    - Uses `close` column when present, otherwise looks for common variants.
    - Creates `returns` table idempotently and upserts by (ticker, date, return_type)
      using `INSERT OR REPLACE` for SQLite compatibility.
    - If `dry_run` is True returns the computed DataFrame without persisting.
    """
    # Choose DB access path: prefer injected repo adapter, else use legacy
    # conn/db functions
    if repo is None:
        repo = DefaultDatabaseClient()
    # Normalize params and load prices via DB helper
    qstart = _normalize_param(start)
    qend = _normalize_param(end)

    resolved_ticker = ticker
    if isinstance(repo, DefaultDatabaseClient):
        resolved = _db.resolve_existing_ticker(ticker, conn=conn)
        if resolved is not None:
            resolved_ticker = resolved

    df_prices = repo.read_prices(
        resolved_ticker,
        start=qstart,
        end=qend,
        conn=conn,
    )
    if df_prices.empty:
        return pd.DataFrame() if dry_run else None

    # Use shared helpers for selection, computation and assembly
    price_col = _choose_price_column(df_prices)
    returns = _compute_returns_series(df_prices, price_col)

    if returns.empty:
        return pd.DataFrame() if dry_run else None

    out_df = _build_out_df(returns, resolved_ticker)

    if dry_run:
        return out_df
    # Persist results and record telemetry
    _persist_returns(out_df, resolved_ticker, repo=repo, conn=conn)
    return out_df


def _normalize_param(p: Optional[Union[str, date, datetime]]) -> Optional[str]:
    if p is None:
        return None
    if isinstance(p, (datetime, date)):
        return p.strftime("%Y-%m-%d")
    if isinstance(p, str):
        return p
    raise TypeError("start/end must be str, date, datetime or None")


def _choose_price_column(df: pd.DataFrame) -> str:
    """Return the preferred price column name from DataFrame or raise KeyError."""
    for c in ("adj_close", "Adj Close", "close", "Close"):
        if c in df.columns:
            return c
    raise KeyError(
        "Nenhuma coluna de preço encontrada em `prices` para cálculo "
        "de retornos"
    )


def _compute_returns_series(df: pd.DataFrame, price_col: str) -> pd.Series:
    """Compute pct-change returns ensuring datetime index and chronological order.

    This enforces that the input DataFrame has a datetime-like index and sorts
    it chronologically before computing percentage change so downstream code
    can safely interpret the Series index as dates.
    """
    # Work on a copy sorted by index to guarantee chronological pct_change
    df_sorted = df.sort_index()

    # Best-effort validation: ensure index is datetime-like
    try:
        pd.to_datetime(df_sorted.index)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Expected DataFrame index to be datetime-like for return computation, "
            f"but got index of type {type(df_sorted.index).__name__}"
        ) from exc

    return df_sorted[price_col].astype(float).pct_change().dropna()


def _build_out_df(returns: pd.Series, ticker: str) -> pd.DataFrame:
    out_df = returns.rename("return_value").to_frame()
    out_df["ticker"] = ticker
    out_df["return_type"] = "daily"
    out_df["created_at"] = now_utc_iso()
    return out_df.reset_index()


def _persist_returns(
    out_df: pd.DataFrame,
    ticker: str,
    repo: Optional[DatabaseClient] = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    job_id = uuid.uuid4().hex
    start_ts = time.time()
    if repo is None:
        repo = DefaultDatabaseClient()
    # canonicalize ticker column if present
    if "ticker" in out_df.columns:
        out_df = out_df.copy()
        # drop the optional ".SA" suffix before writing to DB
        out_df["ticker"] = (
            out_df["ticker"].astype(str).str.replace(".SA", "", regex=False)
        )
    repo.write_returns(out_df, conn=conn, return_type="daily")
    duration_ms = int((time.time() - start_ts) * 1000)
    rows_written = len(out_df)
    logger.info(
        "persisted_returns",
        extra={
            "job_id": job_id,
            "ticker": ticker,
            "rows_written": rows_written,
            "duration_ms": duration_ms,
        },
    )
    # Metrics: increment a counter and observe duration histogram (no-op when
    # prometheus_client not installed).
    try:
        metrics.increment_counter("compute_returns_total")
        metrics.observe_histogram("compute_returns_duration_ms", float(duration_ms))
    except Exception:
        logger.debug("metrics recording failed", exc_info=True)
    with contextlib.suppress(Exception):
        repo.record_snapshot_metadata(
            {
                "job_id": job_id,
                "action": "compute_returns",
                "ticker": ticker,
                "rows_written": rows_written,
                "duration_ms": duration_ms,
                "created_at": now_utc_iso(),
            },
            conn=conn,
        )


# `_read_price_series` removed: compute_returns uses `db.read_prices` now


def r_linear(
    p_fin: Union[float, int, pd.Series, np.ndarray],
    p_ini: Union[float, int, pd.Series, np.ndarray],
) -> Union[float, pd.Series, np.ndarray]:
    """Calcula retorno linear (p_fin / p_ini) - 1.

    Suporta scalars e pandas Series/arrays.
    """
    return (p_fin / p_ini) - 1


def r_log(
    p_fin: Union[float, int, pd.Series, np.ndarray],
    p_ini: Union[float, int, pd.Series, np.ndarray],
) -> Union[float, pd.Series, np.ndarray]:
    """Calcula retorno logarítmico: ln(p_fin / p_ini)."""
    return np.log(p_fin / p_ini)


def retorno_periodo(_df: pd.DataFrame) -> Tuple[float, float, float]:
    """Calcula retorno do período a partir de um DataFrame com coluna de preço.

    Retorna uma tupla: (retorno_total, retorno_medio_diario, desvio)
    """
    df = _df.copy()
    price_col = next(
        (
            c
            for c in ("adj_close", "Adj Close", "close", "Close")
            if c in df.columns
        ),
        None,
    )
    if price_col is None:
        raise KeyError("Nenhuma coluna de preço encontrada")

    df["Retorno dia"] = r_log(df[price_col], df[price_col].shift(1))
    ret_periodo = float(df["Retorno dia"].sum())
    ret_medio = float(df["Retorno dia"].mean())
    desvio = float(df["Retorno dia"].std())
    return ret_periodo, ret_medio, desvio


def conv_retorno(rt_p: float, total_periodos: int) -> float:
    """Converte retorno médio para retorno em outro período (ex.: anualização)."""
    return ((1 + rt_p) ** total_periodos) - 1


def conv_risco(ris_p: float, total_periodos: int) -> float:
    """Converte desvio padrão entre períodos usando raiz quadrada do tempo."""
    return ris_p * math.sqrt(total_periodos)


def coef_var(risco: float, ret_medio: float) -> float:
    """Coeficiente de variação (risco / retorno médio)."""
    return risco / ret_medio


def correlacao(ativos: list[str]) -> pd.DataFrame:
    """Calcula correlação entre ativos a partir dos arquivos CSV em `dados/`.

    Retorna um DataFrame de correlações (pearson).
    """
    new_df = pd.DataFrame()
    for a in ativos:
        try:
            fp = DATA_DIR / f"{a}.csv"
            df1 = pd.read_csv(fp)
        except OSError as e:
            logger.warning("Dados de %s não encontrados: %s", a, e)
            continue
        df1 = df1.rename({"Return": f"{a}"}, axis=1)
        ret_a = df1[f"{a}"]
        new_df[f"{a}"] = ret_a.copy()
    return new_df.corr(method="pearson")
