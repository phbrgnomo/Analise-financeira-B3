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
import os
import re
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
    df: pd.DataFrame | None = None
    try:
        import yfinance as yf  # type: ignore

        result = yf.download(ticker, start=start, end=end)
        if result is None:
            print(f"Warning: yfinance retornou None para {ticker}.", file=sys.stderr)
            df = pd.DataFrame()
        else:
            df = result

        if df.empty:
            print(
                f"Warning: yfinance retornou DataFrame vazio para {ticker}.",
                file=sys.stderr,
            )
            print(f"Intervalo: {start} - {end}", file=sys.stderr)
    except Exception as yf_exc:
        print("yfinance não disponível ou falhou:", yf_exc, file=sys.stderr)
        raise

    # Garantir que `df` seja um DataFrame (não None) antes de acessar membros
    if df is None:
        df = pd.DataFrame()

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
        # Provider may expose "Adj Close", but the persisted schema
        # does not include it.
        # We keep raw checksum but do not persist `adj_close` in the CSV.
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

    # Reordenar colunas para o esquema persistido (docs/schema.json)
    cols = [
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
        "fetched_at",
        "raw_checksum",
    ]

    # Garantir que existam as colunas esperadas; se o provider expôs "Adj Close"
    # mantemos o valor internamente, mas não persistimos a coluna `adj_close`.
    for c in cols:
        if c not in out.columns:
            out[c] = None

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
    parser.add_argument(
        "--allow-external",
        action="store_true",
        help="Permite salvar fora de dados/samples (use com cuidado)",
    )
    args = parser.parse_args()

    ticker = args.ticker
    # sanitize ticker for filename usage (avoid injection/traversal in filenames)
    safe_ticker = re.sub(r"[^A-Za-z0-9._-]", "_", ticker)
    df = fetch_yahoo(ticker, days=args.days)

    # salvar resposta original (raw) para inspeção
    if df.empty:
        print("Erro: DataFrame bruto vazio do provedor", file=sys.stderr)
        sys.exit(2)

    out_dir = Path("dados") / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_csv = out_dir / f"{safe_ticker}_raw.csv"

    try:
        df.to_csv(raw_csv, index=False)
    except Exception as exc:
        print(f"Warning: não foi possível salvar CSV bruto: {exc}", file=sys.stderr)

    canonical, raw_checksum = to_canonical(df, ticker)
    default_name = f"{safe_ticker}_sample.csv"

    # Sanitizar e validar `--outfile` para evitar path traversal.
    # Perform validation using os.path on the raw string before creating any Path.
    if args.outfile:
        try:
            out_path_str = _validate_and_nomalize_outfile(
                args.outfile,
                out_dir,
                args.allow_external,
            )
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(2)
    else:
        out_path_str = str(out_dir / default_name)

    parent_dir = os.path.dirname(out_path_str)
    os.makedirs(parent_dir, exist_ok=True)
    canonical.to_csv(out_path_str, index=False)

    print(f"Amostra salva em: {out_path_str}")
    print(f"raw_checksum: {raw_checksum}")


# TODO Rename this here and in `main`
def _validate_and_nomalize_outfile(
    outfile: str,
    out_dir: Path,
    allow_external: bool,
) -> str:
    """Validate and normalize an --outfile value.

    Returns a resolved path string or raises ValueError on invalid input.
    This helper does not perform CLI termination; callers should convert
    exceptions to exit codes as appropriate.
    """
    if not isinstance(outfile, str):
        raise ValueError("Invalid --outfile value")

    raw = outfile
    if "\x00" in raw:
        raise ValueError("Invalid --outfile: contains null byte")

    normalized = os.path.normpath(raw)
    is_abs = os.path.isabs(raw)

    if not allow_external:
        allowed_dir = str(out_dir.resolve())

        if is_abs:
            real = os.path.realpath(raw)
            try:
                common = os.path.commonpath([real, allowed_dir])
            except ValueError as err:
                raise ValueError(
                    (
                        "Refusing to write output outside of dados/samples."
                        " Use --allow-external to override."
                    )
                ) from err
            if common != allowed_dir:
                raise ValueError(
                    (
                        "Refusing to write output outside of dados/samples."
                        " Use --allow-external to override."
                    )
                )
            resolved_out = real
        else:
            # relative: disallow traversal
            if ".." in normalized.split(os.path.sep):
                raise ValueError(
                    (
                        "Refusing to write output outside of dados/samples."
                        " Use --allow-external to override."
                    )
                )
            resolved_out = os.path.join(allowed_dir, normalized.lstrip(os.path.sep))
    else:
        # allow external: canonicalize
        resolved_out = os.path.realpath(raw)

    return resolved_out


if __name__ == "__main__":
    main()
