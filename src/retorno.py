import math
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Tuple, Union

import numpy as np
import pandas as pd

import src.db as db
from src.paths import DATA_DIR


def compute_returns(
    ticker: str,
    start: object = None,
    end: object = None,
    conn: sqlite3.Connection | None = None,
    dry_run: bool = False,
) -> pd.DataFrame | None:
    """Compute simple daily returns for `ticker` and persist to `returns` table.

    - Reads `prices` from provided `conn` (sqlite3.Connection). If `conn` is None,
      raises ValueError (caller should inject connection in tests/CLI).
    - Uses `close` column when present, otherwise looks for common variants.
    - Creates `returns` table idempotently and upserts by (ticker, date, return_type)
      using `INSERT OR REPLACE` for SQLite compatibility.
    - If `dry_run` is True returns the computed DataFrame without persisting.
    """
    if conn is None:
        raise ValueError(
            "compute_returns requires a sqlite3.Connection via conn parameter"
        )

    # Read price series using helper to keep complexity low
    series = _read_price_series(ticker, start, end, conn)
    returns = series.pct_change().dropna()

    if returns.empty:
        # Nothing to persist
        if dry_run:
            return pd.DataFrame()
        return None

    out_df = returns.rename("return").to_frame()
    out_df["ticker"] = ticker
    out_df["return_type"] = "daily"
    out_df["created_at"] = datetime.utcnow().isoformat()
    out_df = out_df.reset_index()  # date becomes a column again

    if dry_run:
        return out_df

    # Telemetry: record job id, rows written, duration
    job_id = uuid.uuid4().hex
    start_ts = time.time()

    # Delegate persistence to DB layer
    db.write_returns(out_df, conn=conn, return_type="daily")

    duration_ms = int((time.time() - start_ts) * 1000)
    rows_written = len(out_df)

    # Record metadata/telemetry using DB helper (stores into snapshots table)
    try:
        db.record_snapshot_metadata(
            {
                "job_id": job_id,
                "action": "compute_returns",
                "ticker": ticker,
                "rows_written": rows_written,
                "duration_ms": duration_ms,
                "created_at": datetime.utcnow().isoformat(),
            },
            conn=conn,
        )
    except Exception:
        # Telemetry should not break main flow; swallow errors gracefully
        pass

    return out_df


def _read_price_series(ticker, start, end, conn: sqlite3.Connection) -> pd.Series:
    """Read a single price series from `prices` table choosing the best price
    column available. Returns a pandas Series indexed by date.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(prices)")
    cols = [row[1] for row in cur.fetchall()]
    price_col = None
    for c in ("adj_close", "Adj Close", "close", "Close"):
        if c in cols:
            price_col = c
            break
    if price_col is None:
        raise KeyError(
            "Nenhuma coluna de preço encontrada em `prices` para cálculo de retornos"
        )

    sql = f"SELECT date, {price_col} as price FROM prices WHERE ticker = ?"
    params = [ticker]
    if start is not None:
        sql += " AND date >= ?"
        params.append(str(start))
    if end is not None:
        sql += " AND date <= ?"
        params.append(str(end))
    sql += " ORDER BY date"

    df = pd.read_sql_query(sql, conn, params=params, parse_dates=["date"])
    if df.empty:
        return pd.Series(dtype=float)
    df = df.set_index("date")
    return df["price"].astype(float)


def r_linear(
    p_fin: Union[float, int, pd.Series, np.ndarray],
    p_ini: Union[float, int, pd.Series, np.ndarray],
) -> Union[float, pd.Series]:
    """Calcula retorno linear (p_fin / p_ini) - 1.

    Suporta scalars e pandas Series/arrays.
    """
    return (p_fin / p_ini) - 1


def r_log(
    p_fin: Union[float, int, pd.Series, np.ndarray],
    p_ini: Union[float, int, pd.Series, np.ndarray],
) -> Union[float, pd.Series]:
    """Calcula retorno logarítmico: ln(p_fin / p_ini)."""
    return np.log(p_fin / p_ini)


def retorno_periodo(_df: pd.DataFrame) -> Tuple[float, float, float]:
    """Calcula retorno do período a partir de um DataFrame com coluna de preço.

    Retorna uma tupla: (retorno_total, retorno_medio_diario, desvio)
    """
    df = _df.copy()
    # Preferência por colunas ajustadas
    price_col = None
    for c in ("adj_close", "Adj Close", "close", "Close"):
        if c in df.columns:
            price_col = c
            break
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
        except (FileNotFoundError, OSError) as e:
            print(f"Dados de {a} não encontrados: {e}")
            continue
        df1.rename({"Return": f"{a}"}, axis=1, inplace=True)
        ret_a = df1[f"{a}"]
        new_df[f"{a}"] = ret_a.copy()
    return new_df.corr(method="pearson")
