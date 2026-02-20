#!/usr/bin/env python3
"""
Puxa uma amostra de um ticker do Yahoo (via yfinance) e mapeia para
o esquema canônico:
(ticker,date,open,high,low,close,adj_close,volume,source,fetched_at,raw_checksum)
Salva um CSV em dados/samples.

Uso:
  python scripts/pull_sample.py PETR4.SA --days 5

Observações:
- Requer pandas e yfinance instalados no ambiente (poetry install).
- Se a importação falhar, a mensagem explicará como resolver.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover - runtime dependency
    print("Erro: pandas é necessário.", file=sys.stderr)
    print("Instale via 'poetry install'. Detalhe:", exc, file=sys.stderr)
    sys.exit(2)


def fetch_yahoo(ticker: str, days: int = 5) -> pd.DataFrame:
    """Busca dados históricos do Yahoo para o ticker nos últimos `days` dias.

    Usa `yfinance` como provider primário. OBS: `pandas_datareader` não é
    suportado em Python 3.12 por causa da remoção de `distutils`; por isso
    o projeto requer `yfinance` para integração com o Yahoo Finance.
    """
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    print(f"start:{start}, end:{end}, days:{days}")

    # Tentar yfinance primeiro (import local)
    try:
        import yfinance as yf  # type: ignore

        df = yf.download(ticker, start=start, end=end)

        if df.empty:
            print(
                f"Warning: yfinance retornou DataFrame vazio para {ticker}.",
                file=sys.stderr,
            )
            print(f"Intervalo: {start} - {end}", file=sys.stderr)
    except Exception as yf_exc:
        print("yfinance não disponível ou falhou:", yf_exc, file=sys.stderr)
        raise

    # Garantir coluna Date disponível
    if "Date" not in df.columns:
        df = df.reset_index()
    return df


def to_canonical(df: pd.DataFrame, ticker: str) -> tuple[pd.DataFrame, str]:
    """Converte o DataFrame do provedor para o esquema canônico.

    Retorna (df, raw_checksum).
    raw_checksum é o SHA256 do CSV bruto do provedor (sem índice).
    """
    mapping = {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }

    # Preparar saída
    out = pd.DataFrame()
    for src, dst in mapping.items():
        out[dst] = df[src] if src in df.columns else None
    out["ticker"] = ticker
    out["source"] = "yahoo"
    now_utc = datetime.now(timezone.utc).replace(tzinfo=timezone.utc)
    fetched_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    out["fetched_at"] = fetched_at

    # Normalizar date
    try:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    except Exception:
        out["date"] = out["date"].astype(str)

    # Calcular checksum do CSV bruto do provedor
    raw_csv = df.to_csv(index=False).encode("utf-8")
    raw_checksum = hashlib.sha256(raw_csv).hexdigest()
    out["raw_checksum"] = raw_checksum

    # Reordenar colunas para o canonical schema
    cols = [
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "source",
        "fetched_at",
        "raw_checksum",
    ]
    out = out[cols]
    return out, raw_checksum


def main() -> None:
    parser = argparse.ArgumentParser(description="Puxa amostra do Yahoo e salva CSV.")
    parser.add_argument("ticker", help="Ticker (ex.: PETR4.SA)")
    parser.add_argument(
        "--days",
        type=int,
        default=10,
        help="Número de dias (default: 10)",
    )
    parser.add_argument(
        "--outfile",
        type=str,
        default=None,
        help="Caminho do CSV de saída (padrão: dados/samples/{ticker}_sample.csv)",
    )
    args = parser.parse_args()

    ticker = args.ticker
    df = fetch_yahoo(ticker, days=args.days)

    # salvar resposta original (raw) para inspeção
    if df.empty:
        print("Erro: DataFrame bruto vazio do provedor", file=sys.stderr)
        sys.exit(2)

    out_dir = Path("dados") / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_csv = out_dir / f"{ticker}_raw.csv"

    try:
        df.to_csv(raw_csv, index=False)
    except Exception as exc:
        print(f"Warning: não foi possível salvar CSV bruto: {exc}", file=sys.stderr)

    canonical, raw_checksum = to_canonical(df, ticker)
    default_name = f"{ticker}_sample.csv"
    # Saída fixa para simplificar uso em scripts de teste
    out_path = out_dir / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(out_path, index=False)

    print(f"Amostra salva em: {out_path}")
    print(f"raw_checksum: {raw_checksum}")


if __name__ == "__main__":
    main()
