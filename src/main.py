from datetime import date, timedelta
from typing import Optional

import typer

from src.paths import DATA_DIR

# Instância principal da aplicação de linha de comando usando Typer
app = typer.Typer()

d_atual = date.today()


def _fetch_and_prepare_asset(
    a: str,
    d_in: str,
    d_fim: str,
    validation_tolerance: Optional[float],
) -> None:
    """Helper to fetch, persist raw, map to canonical and validate an asset."""

    from datetime import datetime
    from datetime import timezone as _tz

    import src.dados_b3 as dados
    from src.ingest.pipeline import save_raw_csv

    try:
        df = dados.cotacao_ativo_dia(a, d_in, d_fim)
    except Exception as e:
        print(f"Problemas baixando dados: {e}")
        return

    ts_raw = datetime.now(_tz.utc).strftime("%Y%m%dT%H%M%SZ")
    save_meta = save_raw_csv(df, "yfinance", f"{a}.SA", ts_raw)
    if save_meta.get("status") != "success":
        print(f"Falha ao salvar raw para {a}: {save_meta.get('error_message')}")
        return

    try:
        from src.etl.mapper import to_canonical

        canonical = to_canonical(
            df,
            provider_name="yfinance",
            ticker=f"{a}.SA",
            raw_checksum=save_meta.get("raw_checksum"),
            fetched_at=save_meta.get("fetched_at"),
        )
        print(f"Mapper produced {len(canonical)} canonical rows for {a}")
        # provide a fallback so the `except ValidationError` clause is valid
        # even if the import fails during static analysis or runtime
        ValidationError = Exception
        try:
            from src.validation import ValidationError, validate_and_handle

            valid_df, invalid_df, summary, details = validate_and_handle(
                canonical,
                provider="yfinance",
                ticker=f"{a}.SA",
                raw_file=save_meta.get("filepath") or "",
                ts=save_meta.get("fetched_at") or "",
                raw_root="raw",
                metadata_path="metadata/ingest_logs.json",
                threshold=validation_tolerance,
                abort_on_exceed=True,
                persist_invalid=True,
            )

            print(
                "Validation summary for %s: rows_total=%d, rows_valid=%d, "
                "rows_invalid=%d, invalid_percent=%.4f"
                % (
                    a,
                    summary.rows_total,
                    summary.rows_valid,
                    summary.rows_invalid,
                    summary.invalid_percent,
                )
            )
        except ValidationError as e:
            print(f"Ingest aborted for {a} due to validation threshold: {e}")
            return
        except Exception as e:
            print(f"Validation step failed for {a}: {e}")

    except Exception as e:
        print(f"Mapper failed for {a}: {e}")

    # Calcula o retorno (usa coluna ajustada quando disponível, senão `close`)
    import src.retorno as rt

    price_candidates = ("Adj Close", "adj_close", "Close", "close")
    price_col = next((c for c in price_candidates if c in df.columns), None)
    if price_col is not None:
        df["Return"] = rt.r_log(df[price_col], df[price_col].shift(1))
    else:
        df["Return"] = None

    # Save CSV for later stats
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_DIR / f"{a}.csv")


def _compute_and_print_stats(a: str) -> None:
    """Compute simple statistics from saved CSV and print them."""
    import pandas as pd

    import src.retorno as rt

    try:
        df = pd.read_csv(DATA_DIR / f"{a}.csv")
    except Exception as e:
        print(f"Dados para {a} não encontrados: {e}")
        return

    retorno_total = df["Return"].sum()
    retorno_medio = df["Return"].mean()
    risco = df["Return"].std()
    retorno_anual = rt.conv_retorno(retorno_medio, 252)
    risco_anual = rt.conv_risco(risco, 252)

    print(f"\n--------{a}--------")
    print(f"Retorno total do período: {round((retorno_total * 100), 4)}%")
    print(f"Retorno médio ao dia: {round((retorno_medio * 100), 4)}%")
    print(f"Risco ao dia: {round((risco * 100), 4)}%")
    print(f"Retorno médio ao ano: {round((retorno_anual * 100), 4)}%")
    print(f"Risco ao ano: {round(risco_anual * 100, 4)}%")
    print(f"Coeficiente de variação(dia):{rt.coef_var(risco, retorno_medio)}")


@app.command()
def main(
    validation_tolerance: Optional[float] = typer.Option(
        None, "--validation-tolerance", help="Tolerância de inválidas (ex: 0.10)"
    ),
):  # noqa: C901
    # importações locais para evitar exigir dependências apenas para `--help`

    import src.retorno as rt

    # ativos_entrada = input(
    #     "Lista de Ativos, separados por vírgula (exemplo: PETR4,BBDC3): "
    # )
    # ativos = ativos_entrada.split(',')
    # data_in = input("Data de inicio (MM-DD-AAAA): ")
    # data_fim = input("Data de fim (MM-DD-AAAA): ")

    # Define ativos a serem pesquisados
    ativos = ["PETR4", "ITUB3", "BBDC4"]

    periodo_dados = 52  # Periodo total dos dados em semanas
    time_skew = timedelta(weeks=periodo_dados)

    d_fim = d_atual.strftime("%m-%d-%Y")
    d_in = (d_atual - time_skew).strftime("%m-%d-%Y")
    print(d_in, d_fim)

    for a in ativos:
        data_path = DATA_DIR / f"{a}.csv"
        if data_path.is_file():
            print(f"Dados encontrados para {a}")
            continue
        print(f"Baixando e preparando dados de {a}")
        _fetch_and_prepare_asset(a, d_in, d_fim, validation_tolerance)

    for a in ativos:
        _compute_and_print_stats(a)

    # Calcula correlação entre os ativos
    newdf = rt.correlacao(ativos)
    print(newdf)


if __name__ == "__main__":
    app()
