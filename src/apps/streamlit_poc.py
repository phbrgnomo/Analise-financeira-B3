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

    if isinstance(df.index, pd.DatetimeIndex) and "date" not in df.columns:
        df = df.reset_index()
        date_col = df.columns[0]
        if date_col != "date":
            df = df.rename(columns={date_col: "date"})
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            df = df[["date"] + numeric_cols[:1]]
    if df.empty:
        return
    st.line_chart(
        df[["date", df.select_dtypes(include="number").columns[0]]],
        x="date",
        y=df.select_dtypes(include="number").columns[0],
    )


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


def _extract_date_range(df: pd.DataFrame) -> tuple[Optional[str], Optional[str]]:
    """Return (start_date, end_date) ISO strings or (None, None).

    Encapsulates the multiple try/except branches used to infer a
    date range from an explicit 'date' column or from the index.
    """
    rows = int(len(df))
    # Prefer an explicit 'date' column
    if "date" in df.columns:
        try:
            ser = pd.to_datetime(df["date"], errors="coerce").dropna()
            if not ser.empty:
                return ser.min().date().isoformat(), ser.max().date().isoformat()
        except Exception:
            return None, None

    # Try the index as datetime-like
    try:
        idx = pd.to_datetime(df.index, errors="coerce")
        idx_clean = idx.dropna()
        if len(idx_clean) > 0:
            return (
                idx_clean.min().date().isoformat(),
                idx_clean.max().date().isoformat(),
            )
    except Exception:
        pass

    # Fallback to stringified first/last index values if possible
    try:
        if rows > 0:
            return str(df.index[0]), str(df.index[-1])
    except Exception:
        pass
    return None, None


def _first_snapshot_checksum_or_none(df: pd.DataFrame) -> Optional[str]:
    """Return first non-null 'snapshot_checksum' value or None."""
    if "snapshot_checksum" not in df.columns:
        return None
    try:
        val = df["snapshot_checksum"].dropna()
        if not val.empty:
            return str(val.iloc[0])
    except Exception:
        return None
    return None


def compute_summary_stats(df: pd.DataFrame):
    """Compute small summary of a loaded prices DataFrame.

    Returns a tuple: (rows, start_date, end_date, checksum).

    - rows: number of rows (int)
    - start_date / end_date: ISO date string (YYYY-MM-DD) or None
    - checksum: first non-null 'snapshot_checksum' value if present,
      otherwise a SHA1 hex digest computed from df.to_csv(index=False).

    This function is pure (no Streamlit imports) so it is safe to
    import in tests.
    """
    rows = int(len(df))
    start_date, end_date = _extract_date_range(df)

    checksum = _first_snapshot_checksum_or_none(df)
    if not checksum:
        # Deterministic fallback: sha1 of CSV text without index
        import hashlib

        csv = df.to_csv(index=False)
        checksum = hashlib.sha1(csv.encode("utf-8")).hexdigest()

    return rows, start_date, end_date, checksum


def _sidebar_and_inputs(st) -> tuple[str, Optional[date], Optional[date], bool]:
    """Handle sidebar controls and return (ticker, start, end, abort).

    The helper centralizes branching around sidebar inputs so main() has
    fewer decision points and remains import-safe (st is passed in).
    """
    st.sidebar.header("Controles")
    # Forçar reload (POC): apenas sinaliza a intenção, não executa reload
    force_reload = st.sidebar.checkbox("Forçar reload")
    if force_reload:
        st.info(
            "Forçar reload: ao usar, o app tentará recarregar dados "
            "(não implementado nesta POC)"
        )

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

    # If user input is invalid, show message and signal abort
    if start > end:
        st.sidebar.error("Data inicial maior que a data final. Ajuste o intervalo.")
        return "", None, None, True

    if not ticker:
        st.warning("Nenhum dado: selecione ou informe um ticker.")
        return "", None, None, True

    return ticker, start, end, False


def _render_summary_metrics(st, df: pd.DataFrame) -> None:
    """Compute and render small summary metrics above the charts."""
    rows, start_date, end_date, checksum = compute_summary_stats(df)
    checksum_trunc = checksum[:8] if checksum else ""
    if start_date or end_date:
        date_range = f"{start_date or 'N/A'} -> {end_date or 'N/A'}"
    else:
        date_range = "N/A"

    cols = st.columns(3)
    cols[0].metric("Rows", rows)
    cols[1].metric("Date range", date_range)
    cols[2].metric("Checksum", checksum_trunc)


def main() -> None:
    """Constrói a interface Streamlit. Executada apenas quando este arquivo
    for invocado como script (ex.: ``streamlit run src/apps/streamlit_poc.py``).
    """
    import streamlit as st

    st.set_page_config(page_title="POC Streamlit - Dados Financeiros (SQLite)")
    st.title("POC Streamlit — Dados Financeiros (SQLite)")

    # Delegate sidebar and input handling to keep main complexity low
    ticker, start, end, abort = _sidebar_and_inputs(st)
    if abort:
        return

    try:
        df = load_prices(ticker, start=start, end=end)
    except Exception as exc:
        st.error(f"Erro ao carregar dados: {exc}")
        return

    if df.empty:
        st.warning("Nenhum dado encontrado para o período selecionado.")
        return

    _render_summary_metrics(st, df)

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
