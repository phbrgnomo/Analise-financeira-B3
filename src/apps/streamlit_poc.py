"""POC Streamlit app: mostra preços e retornos via camada src.db.prices.

Este módulo foi desenhado para ser "import-safe" em testes: a UI só é
construída quando o arquivo é executado como script (``__main__``). Funções
úteis expostas (ex.: ``load_prices``) delegam à camada de banco
(``src.db.prices.read_prices``) e podem ser importadas em testes sem
instalar/rodar o Streamlit.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Union

import pandas as pd

from src.db.prices import list_price_tickers, read_prices

DataLike = Union[pd.Series, pd.DataFrame]


def load_prices(
    ticker: str, start: Optional[date] = None, end: Optional[date] = None
) -> pd.DataFrame:
    """Carrega preços delegando para src.db.prices.read_prices.

    Parâmetros ``start`` e ``end`` podem ser objetos ``datetime.date``
    (conversão para ISO "YYYY-MM-DD" é feita internamente).
    """
    if not ticker or not ticker.strip():
        return pd.DataFrame()

    start_s = start.isoformat() if start else None
    end_s = end.isoformat() if end else None
    return read_prices(ticker, start=start_s, end=end_s)


def _safe_line_chart(data: DataLike) -> None:
    """Renderiza um gráfico de linhas com Streamlit, importando-o
    de forma preguiçosa para manter o módulo importável em ambientes
    sem Streamlit.
    """
    try:  # import local para não exigir streamlit em tempo de import
        import streamlit as st
    except Exception:  # pragma: no cover - visual helper
        return

    if data is None:
        return
    if isinstance(data, pd.Series):
        df = data.to_frame()
    else:
        df = data
    if df.empty:
        return
    st.line_chart(df)


def _choose_price_series(df: pd.DataFrame) -> pd.Series:
    """Escolhe a série de preço mais adequada do DataFrame.

    Prefere a coluna ``close``, depois a primeira coluna numérica e, por
    fim, a primeira coluna disponível.
    """
    if "close" in df.columns:
        return df["close"]
    numeric_cols = df.select_dtypes(include="number").columns
    if len(numeric_cols) > 0:
        return df[numeric_cols[0]]
    return df.iloc[:, 0]


def main() -> None:
    """Constrói a interface Streamlit. Executada apenas quando este arquivo
    for invocado como script (ex.: ``streamlit run src/apps/streamlit_poc.py``).
    """
    import streamlit as st

    st.set_page_config(page_title="POC Streamlit - Dados Financeiros (SQLite)")
    st.title("POC Streamlit — Dados Financeiros (SQLite)")

    st.sidebar.header("Controles")

    try:
        tickers = list_price_tickers()
    except Exception:
        tickers = []
    options = tickers if tickers else [""]

    selected = st.sidebar.selectbox("Selecione um ticker", options=options)
    typed = st.sidebar.text_input("Ou digite um ticker livre (ex: PETR4)", "")

    ticker = typed.strip().upper() if typed and typed.strip() else (selected or "")

    today = date.today()
    default_start = today - timedelta(days=365)
    start = st.sidebar.date_input("Data inicial", value=default_start)
    end = st.sidebar.date_input("Data final", value=today)

    # date_input can return a list/tuple when multiple values are provided
    if isinstance(start, (list, tuple)):
        start = start[0]
    if isinstance(end, (list, tuple)):
        end = end[0]

    if start > end:
        st.sidebar.error("Data inicial maior que a data final. Ajuste o intervalo.")
        return

    if not ticker:
        st.warning("Nenhum dado: selecione ou informe um ticker.")
        return

    try:
        df = load_prices(ticker, start=start, end=end)
    except Exception as exc:
        st.error(f"Erro ao carregar dados: {exc}")
        return

    if df.empty:
        st.warning("Nenhum dado encontrado para o período selecionado.")
        return

    st.subheader(f"Preço — {ticker}")
    price = _choose_price_series(df)
    _safe_line_chart(price)

    st.subheader("Retornos Diários (%)")
    returns = price.pct_change().dropna()
    if returns.empty:
        st.warning("Nenhum dado de retorno disponível para o período selecionado.")
    else:
        returns_pct = returns * 100
        _safe_line_chart(returns_pct.to_frame("retornos_pct"))


if __name__ == "__main__":
    main()
