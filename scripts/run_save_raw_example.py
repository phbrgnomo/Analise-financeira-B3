#!/usr/bin/env python3
"""
Script simples para demonstrar `save_raw_csv` (Story 1.4).

Este script roda sem argumentos e demonstra a gravação de raw CSV e
registro de metadados para exemplos fixos. Ele imprime feedback
passo-a-passo sobre o que está acontecendo.

Observações:
- Requer `pandas` e dependências do adapter (ex.: `yfinance`).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover - runtime dependency
    print("Erro: pandas é necessário.", file=sys.stderr)
    print("Instale via 'poetry install'. Detalhe:", exc, file=sys.stderr)
    raise

# Importar FetchError no nível do módulo para evitar avisos do analisador (pylance)
from src.adapters.errors import FetchError

# (sem instância global) o adaptador é criado localmente em `fetch_yahoo`


def fetch_yahoo(ticker: str, days: int = 5) -> pd.DataFrame:
    """Busca dados históricos do Yahoo para o ticker nos últimos `days` dias.
    """
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)

    # Criar instância local do adaptador para busca (YFinanceAdapter)
    try:
        from src.adapters.yfinance_adapter import YFinanceAdapter

        adapter = YFinanceAdapter()
        df = adapter.fetch(
            ticker,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )
    except FetchError as fe:
        print(f"Erro ao buscar dados via adapter: {fe}", file=sys.stderr)
        raise
    except Exception as exc:  # pragma: no cover - runtime dependency
        print("Erro inesperado ao usar o adapter yfinance:", exc, file=sys.stderr)
        raise

    # Garantir coluna Date no DataFrame (compatibilidade com pipeline)
    if "Date" not in df.columns:
        df = df.reset_index()
    return df


def main() -> None:
    """Executa exemplos fixos sem argumentos e imprime feedback.

    Exemplos incluídos: `PETR4.SA`, `ITUB3.SA` (últimos 5 dias).
    """
    examples = ["PETR4.SA", "ITUB3.SA"]
    days = 10
    provider = "yfinance"

    # import local para reduzir custo até o uso
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from src.ingest.pipeline import save_raw_csv

    for ticker in examples:
        print(f"\n=== Processando {ticker} (últimos {days} dias) ===")
        try:
            print("Baixando dados via adapter...")
            df = fetch_yahoo(ticker, days=days)
        except Exception as exc:
            print(f"Falha ao baixar {ticker}: {exc}")
            continue

        if df.empty:
            print(f"Nenhum dado para {ticker}, pulando.")
            continue

        ts = _dt.now(_tz.utc).strftime("%Y%m%dT%H%M%SZ")
        print("Salvando raw CSV e calculando checksum...")
        meta = save_raw_csv(df, provider, ticker, ts)

        status = meta.get("status")
        if status != "success":
            err = meta.get("error_message")
            print(f"save_raw_csv retornou erro para {ticker}: {err}")
            continue

        print("Metadados retornados:")
        print(json.dumps(meta, ensure_ascii=False, indent=2))

        fp = Path(meta.get("filepath", ""))
        if fp.exists():
            print(f"Arquivo salvo: {fp}")
            chk = fp.with_suffix(f"{fp.suffix}.checksum")
            if chk.exists():
                print(f"Checksum: {chk.read_text().strip()}")
            else:
                print("Arquivo de checksum não encontrado")
        else:
            print("Arquivo não encontrado após gravação (ver logs)")


if __name__ == "__main__":
    main()
