#!/usr/bin/env python3
"""
Teste integrado: adapter -> mapper

Uso:
  python scripts/test_adapter_mapper.py --ticker PETR4.SA \
    --rows 5 --save out.csv --verbose

Comportamento:
- Instancia o adaptador (YFinanceAdapter) e chama fetch(ticker)
- Passa o DataFrame resultante para src.etl.mapper.to_canonical
- Imprime resumo e opcionalmente salva CSV canônico
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from src.adapters.yfinance_adapter import YFinanceAdapter  # type: ignore
from src.etl.mapper import MappingError, to_canonical  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description="Teste adapter -> mapper (YFinance)")
    parser.add_argument("--ticker", default="PETR4.SA")
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--save", dest="save_path", default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    adapter = YFinanceAdapter()

    try:
        # pass required_columns=[] to bypass strict validation inside the adapter
        # and allow the script to normalize provider output prior to mapping
        df = adapter.fetch(
            args.ticker,
            start_date=None,
            end_date=None,
            required_columns=[],
        )
    except Exception as exc:
        print("Erro ao buscar dados do provider:", exc, file=sys.stderr)
        return 2

    # Normalize provider DataFrame if necessary (e.g., MultiIndex columns from yfinance)
    expected_cols = {"Open", "High", "Low", "Close", "Volume"}

    def _normalize_provider_df(raw: pd.DataFrame) -> pd.DataFrame:
        # If columns are MultiIndex, try to pick the level with expected column names
        if getattr(raw.columns, "nlevels", 1) > 1:
            lvl0 = list(raw.columns.get_level_values(0))
            lvl1 = list(raw.columns.get_level_values(1))
            if any(c in expected_cols for c in lvl0):
                raw.columns = lvl0
                return raw
            if any(c in expected_cols for c in lvl1):
                raw.columns = lvl1
                return raw
            # fallback: join levels
            raw.columns = [
                "_".join([str(x) for x in col if x is not None])
                for col in raw.columns
            ]
            return raw

        # If first row contains a repeated ticker header (some CSV dumps), try
        # to detect and fix (e.g., header row with Unnamed or single column with
        # ticker as second line)
        if raw.columns.tolist()[0] == "Unnamed: 0":
            # possible double header; try reading second row as header is not
            # implemented here — return raw to allow manual inspection
            return raw

        return raw

    df = _normalize_provider_df(df)

    try:
        canonical = to_canonical(df, provider_name="yahoo", ticker=args.ticker)
    except MappingError as e:
        print("MappingError:", e, file=sys.stderr)
        # for debugging, dump columns and types
        print("Provider DF columns:", list(df.columns), file=sys.stderr)
        try:
            print(df.head().to_string(), file=sys.stderr)
        except Exception:
            pass
        return 3

    print("Canonical columns:", list(canonical.columns))
    print(canonical.head().to_string(index=False))
    print("attrs:", canonical.attrs)

    if args.save_path:
        out = Path(args.save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        canonical.to_csv(out, index=False)
        print(f"Salvo CSV canônico em: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
