#!/usr/bin/env python3
"""
Script de teste do canonical mapper.

Uso:
  python scripts/test_mapper.py [--ticker TICKER] [--provider PROVIDER]
                                [--rows N] [--raw-csv PATH] [--save PATH]

Comportamento:
- Gera um DataFrame exemplo (yfinance-like) ou lê um CSV bruto se --raw-csv for
  fornecido.
- Chama src.etl.mapper.to_canonical e imprime um resumo do resultado.
- Sai com código 0 em sucesso, >0 em falhas.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Garantir import do pacote src quando executado a partir do repositório
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.etl.mapper import to_canonical, MappingError  # type: ignore


def make_sample_df(rows: int) -> pd.DataFrame:
    """Cria um DataFrame yfinance-like determinístico para testes."""
    dates = pd.date_range(end=pd.Timestamp.now().normalize(), periods=rows)
    data = {
        "Open": [100.0 + i for i in range(rows)],
        "High": [105.0 + i for i in range(rows)],
        "Low": [99.0 + i for i in range(rows)],
        "Close": [104.0 + i for i in range(rows)],
        "Adj Close": [103.5 + i for i in range(rows)],
        "Volume": [1_000_000 + 100_000 * i for i in range(rows)],
    }
    return pd.DataFrame(data, index=dates)


def read_raw_csv(path: Path) -> pd.DataFrame:
    """Tenta ler CSV bruto de provider de forma tolerante.

    Primeiro tenta read_csv com header padrão, se falhar tenta pular
    a primeira linha (caso alguns dumps incluam metadados).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    try:
        return pd.read_csv(p, index_col=0, parse_dates=True)
    except Exception:
        # tentativa fallback
        return pd.read_csv(p, index_col=0, parse_dates=True, skiprows=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Teste rápido do canonical mapper")
    parser.add_argument("--ticker", default="TEST.SA")
    parser.add_argument("--provider", default="yfinance")
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--raw-csv", dest="raw_csv", default=None)
    parser.add_argument("--save", dest="save_path", default=None)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.raw_csv:
        try:
            raw_df = read_raw_csv(Path(args.raw_csv))
        except Exception as exc:  # pragma: no cover - runtime helper
            print(f"Erro ao ler CSV bruto: {exc}", file=sys.stderr)
            return 2
    else:
        raw_df = make_sample_df(args.rows)

    try:
        canonical = to_canonical(raw_df, provider_name=args.provider, ticker=args.ticker)
    except MappingError as e:
        print(f"MappingError: {e}", file=sys.stderr)
        return 3
    except Exception as e:  # pragma: no cover - unexpected
        print(f"Erro inesperado: {e}", file=sys.stderr)
        return 4

    # Resumo
    print("Canonical DataFrame columns:", list(canonical.columns))
    print(canonical.head().to_string(index=False))
    print("attrs:", canonical.attrs)

    if args.save_path:
        out = Path(args.save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canonical.to_csv(out, index=False)
        print(f"Salvo CSV canônico em: {out}")

    if args.show:
        print(canonical.to_csv(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
