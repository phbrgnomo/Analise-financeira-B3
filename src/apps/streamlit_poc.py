"""Minimal Streamlit POC that reads prices from src.db and renders charts.

This module provides a lightweight UI used by manual QA and a smoke test
that imports the module to ensure no import-time errors. It intentionally
keeps logic simple and delegates data access to src.db.prices functions.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.db import list_price_tickers, read_prices


def load_prices(ticker: str, start: date | None, end: date | None) -> pd.DataFrame:
    """Load prices for ticker between start and end using DB layer.

    Parameters
    ----------
    ticker:
        Ticker string accepted by the DB layer (e.g. 'PETR4' or 'PETR4.SA').
    start, end:
        date objects or None. If provided they are formatted as YYYY-MM-DD
        strings before being forwarded to the DB helper.

    Returns
    -------
    pandas.DataFrame
        DataFrame indexed by date as returned by src.db.prices.read_prices.
    """
    start_s = start.isoformat() if start else None
    end_s = end.isoformat() if end else None
    # Delegate to DB layer — keep this function thin to ease testing.
    return read_prices(ticker, start=start_s, end=end_s)


def _safe_line_chart(data: pd.DataFrame | pd.Series, label: str) -> None:
    """Render a line chart given a DataFrame or Series using st.line_chart.

    Accept both pandas.DataFrame and pandas.Series. If a Series is passed we
    convert it to a one-column DataFrame using the provided label as
    column name so Streamlit renders a consistent chart. Falls back to
    printing a small table if the data is empty or plotting fails.
    """
    if data is None:
        st.warning(f"Nenhum dado disponível para {label}.")
        return

    # normalize Series -> DataFrame for predictable plotting
    if isinstance(data, pd.Series):
        df = data.to_frame(name=label)
    else:
        df = data

    if df.empty:
        st.warning(f"Nenhum dado disponível para {label}.")
        return

    try:
        st.line_chart(df)
    except Exception:
        # Fallback: render the first few rows so the user can inspect data
        st.write(df.head())


def main() -> None:
    """Main entrypoint for Streamlit app.

    Designed to be safe on import (no heavy work at import-time) so tests can
    import the module for smoke without starting Streamlit server.
    """
    st.set_page_config(page_title="POC Streamlit - Dados Financeiros (SQLite)")

    st.sidebar.title("Controles")
    # Populate ticker selectbox via DB helper. If DB has no tickers this will
    # be an empty list and the user can type a free-form ticker below.
    tickers = list_price_tickers() or []
    selected = st.sidebar.selectbox("Ticker (da base)", [""] + tickers)
    free_ticker = st.sidebar.text_input("Ou digite um ticker")

    today = date.today()
    default_start = today - timedelta(days=365)
    start_date = st.sidebar.date_input("Start date", value=default_start)
    end_date = st.sidebar.date_input("End date", value=today)

    # choose ticker: prefer free text if provided, else selected from list
    ticker = free_ticker.strip() or selected
    if not ticker:
        st.info("Escolha um ticker no seletor ou digite um ticker livre.")
        return

    # Load data and render charts when user interacts with controls
    df = load_prices(ticker, start_date, end_date)

    if df is None or df.empty:
        # Acceptance criteria: show warning with Portuguese "Nenhum dado"
        st.warning("Nenhum dado disponível para o período selecionado.")
        return

    # Prefer column named close/Close/adjclose — try common variants
    close_col = None
    for candidate in ("close", "Close", "adjclose", "Adj Close", "close_adj"):
        if candidate in df.columns:
            close_col = candidate
            break

    if close_col:
        price_series = df[close_col]
    else:
        # If there's no obvious close column, try numeric columns
        numeric = df.select_dtypes("number")
        if not numeric.empty:
            price_series = numeric.iloc[:, 0]
        else:
            st.warning("Nenhum dado numérico disponível para plotagem.")
            return

    st.header(f"Preços: {ticker}")
    _safe_line_chart(price_series, label="preços")

    # Daily returns: pct_change on the price series
    returns = price_series.pct_change().dropna()
    st.header("Retornos diários")
    _safe_line_chart(returns, label="retornos")


if __name__ == "__main__":
    main()
