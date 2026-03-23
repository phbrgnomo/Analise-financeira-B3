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

from src.db.prices import delete_ticker_prices, list_price_tickers, read_prices
from src.search.ticker_search import suggest_tickers

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


def _sidebar_ticker_widget(st, tickers: list[str]) -> str:  # noqa: C901
    """Render a single text input with fuzzy suggestion buttons in sidebar.

    Returns the normalized/uppercased ticker string from the widget
    (possibly empty).
    """
    # Ensure session state keys
    if "ticker_input" not in st.session_state:
        st.session_state["ticker_input"] = ""

    def _ticker_on_change() -> None:  # callback when text input changes
        import time

        st.session_state["_ticker_last_changed"] = time.time()

    # Create the text input (value stored in st.session_state)
    st.sidebar.text_input("Ticker", key="ticker_input", on_change=_ticker_on_change)

    query = (st.session_state.get("ticker_input") or "").strip().upper()

    # Debounce logic: wait 300ms before running fuzzy suggestions
    import time

    debounce_seconds = 0.3
    last_changed = st.session_state.get("_ticker_last_changed")

    suggestions: list[tuple[str, int | None]] = []
    if query:
        if last_changed is not None and (time.time() - last_changed) < debounce_seconds:
            st.sidebar.info("Aguardando digitação...")
        else:
            try:
                candidates = suggest_tickers(query, limit=6)
            except Exception:
                candidates = []
            from difflib import SequenceMatcher

            for c in candidates:
                score = int(SequenceMatcher(a=query, b=c).ratio() * 100)
                suggestions.append((c, score))
    else:
        recent = []
        try:
            recent = (tickers[-6:][::-1]) if tickers else []
        except Exception:
            recent = []
        suggestions = [(c, None) for c in recent]

    if suggestions:
        container = st.sidebar.container()
        cols = container.columns(len(suggestions))
        for idx, (tck, score) in enumerate(suggestions):
            label = f"{tck} ({score}%)" if score is not None else tck
            key = f"suggest_{tck}_{idx}"
            if cols[idx].button(label, key=key):
                st.session_state["ticker_input"] = tck
                st.session_state["_ticker_last_changed"] = time.time()
                st.rerun()

    return query


def _sidebar_delete_controls(st, ticker: str) -> bool:
    """Handle delete-confirm UI in the sidebar for a given ticker.

    Returns True when deletion occurred and the caller should abort the
    main rendering (clears selection). Returns False otherwise.
    """
    if not ticker:
        return False

    if "delete_confirm" not in st.session_state:
        st.session_state.delete_confirm = False

    # Primeiro clique: ativar confirmação
    if not st.session_state.delete_confirm:
        if st.sidebar.button("Excluir dados", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.sidebar.warning(f"Confirmar exclusão de dados do ticker {ticker}?")
        col1, col2 = st.sidebar.columns(2)
        if col1.button("Confirmar exclusão", type="primary"):
            try:
                rows = delete_ticker_prices(ticker)
            except Exception as exc:  # pragma: no cover - DB error
                st.sidebar.error(f"Erro ao deletar dados: {exc}")
                st.session_state.delete_confirm = False
                st.rerun()
                return False
            st.session_state.delete_confirm = False
            st.sidebar.success(f"{rows} linhas deletadas.")
            return True
        if col2.button("Cancelar"):
            st.session_state.delete_confirm = False
            st.rerun()

    return False


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

    # Render ticker input + fuzzy suggestions using helper
    ticker = _sidebar_ticker_widget(st, tickers)

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

    # Deletion controls handled in helper to reduce cyclomatic complexity
    if _sidebar_delete_controls(st, ticker):
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

    # Persist and show currently selected ticker in the page title.
    # Use session_state so the selection survives reruns and the title can
    # be updated dynamically when the user changes the ticker.
    current_ticker = st.session_state.get("current_ticker", "")
    st.set_page_config(
        page_title=(
            f"POC Streamlit - {current_ticker}" if current_ticker else "POC Streamlit"
        ),
        page_icon="📈",
    )
    st.title(
        f"📈 POC Streamlit - {current_ticker}" if current_ticker else "📈 POC Streamlit"
    )

    # Delegate sidebar and input handling to keep main complexity low
    ticker, start, end, abort = _sidebar_and_inputs(st)

    # Persist selection in session_state so the title updates across runs.
    # If the ticker changed, update session_state and trigger a rerun so
    # the page title (and page config) at the top reflect the new value.
    if st.session_state.get("current_ticker") != ticker:
        st.session_state["current_ticker"] = ticker
        # Rerun immediately so set_page_config and st.title at the top
        # are re-executed with the updated session_state value.
        st.rerun()

    if abort:
        return

    try:
        # Show phased feedback during the fetch/process/save workflow.
        # Keep imports local so the module remains import-safe for tests.
        import time

        from src.ingest.raw_storage import DEFAULT_DB

        try:
            from src.services.ingest_service import ensure_prices  # type: ignore
        except Exception:
            ensure_prices = None

        start_t = time.time()
        provider = "yfinance"

        phase1 = st.empty()
        phase2 = st.empty()
        phase3 = st.empty()

        # Phase 1: fetching
        phase1.info(f"🔍 Buscando dados de {provider}...")
        # Ensure start/end are present (should be validated by sidebar)
        assert start is not None and end is not None
        if ensure_prices is None:
            st.warning("Serviço de ingestão não disponível; pulando fetch.")
            res = {"ok": True, "rows_added": 0}
        else:
            res = ensure_prices(
                ticker,
                start=start.isoformat(),
                end=end.isoformat(),
                provider=provider,
                db_path=str(DEFAULT_DB),
            )
        phase1.empty()

        # If ensure_prices reported errors, surface them and stop.
        if not res.get("ok", False):
            err_msg = "; ".join(res.get("errors") or []) or "unknown error"
            phase2.info("⚙️ Processando dados...")
            # attempt to load any existing data for best-effort display
            df = load_prices(ticker, start=start, end=end)
            phase2.empty()
            phase3.info("💾 Salvando no banco...")
            phase3.empty()

            elapsed = time.time() - start_t
            st.error(f"❌ Erro: {err_msg}")
            st.info(f"Tempo decorrido: {elapsed:.1f}s")
            return

        # Phase 2: processing (read latest data and compute summaries)
        phase2.info("⚙️ Processando dados...")
        df = load_prices(ticker, start=start, end=end)
        phase2.empty()

        # Phase 3: saving (persistence already performed by ensure_prices)
        phase3.info("💾 Salvando no banco...")
        phase3.empty()

        elapsed = time.time() - start_t
        rows = res.get("rows_added") or len(df)
        st.success(f"✅ Concluído em {elapsed:.1f}s: {rows} linhas processadas")
    except Exception as exc:
        st.error(f"❌ Erro: {exc}")
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
