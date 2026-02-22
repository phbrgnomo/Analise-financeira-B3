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
    """Fetch, persist raw data, map to canonical schema and optionally validate.

    Parameters
    ----------
    a : str
        Símbolo do ativo (ex.: 'PETR4').
    d_in : str
        Data inicial no formato esperado pelo provedor (ex.: 'MM-DD-YYYY').
    d_fim : str
        Data final no formato esperado pelo provedor (ex.: 'MM-DD-YYYY').
    validation_tolerance : Optional[float]
        Percentual (0.0-1.0) limite de linhas inválidas aceitáveis para não
        abortar o ingest; `None` significa não aplicar threshold.

    Side effects
    ------------
    - Faz download dos dados do provedor (via `src.dados_b3.cotacao_ativo_dia`).
    - Persiste CSV bruto via `save_raw_csv` em `raw/<provider>/...`.
    - Mapeia os dados para o esquema canônico com `to_canonical`.
    - Se o módulo de validação estiver disponível, executa validação
      (chama `validate_and_handle`) que pode persistir linhas inválidas e
      registrar entradas em `metadata/ingest_logs.json`.
    - Calcula a coluna `Return` (log-return) e salva um CSV em `DATA_DIR/{a}.csv`.

    Errors / raises
    ----------------
    - Esta função captura exceções de download, mapeamento e persistência e
      imprime mensagens de erro, retornando `None` para interromper o fluxo
      daquele ativo; erros de baixo nível de DB/FS podem propagar se não
      tratados internamente.
    - Quando a validação excede o threshold e a função de validação aborta,
      o ingest é interrompido para aquele ativo.

    Returns
    -------
    None

    Notes
    -----
    - A função é intencionalmente tolerante a dependências ausentes: o
      módulo de validação é importado dinamicamente e ignorado se não
      estiver disponível, permitindo execução em ambientes leves.
    """

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

    # Mapping: keep failures local and return early if mapper fails
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
    except Exception as e:
        print(f"Mapper failed for {a}: {e}")
        return

    # Validation: import helpers if available and run validation separately
    try:
        from src.validation import ValidationError, validate_and_handle
    except Exception:
        validate_and_handle = None
        ValidationError = None

    if validate_and_handle is None:
        print("Validation module not available; skipping validation step")
    else:
        try:
            _valid_df, _invalid_df, summary, _details = validate_and_handle(
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
        except Exception as e:
            # Avoid using `except ValidationError` when `ValidationError` may
            # be None (not imported). Distinguish validation-threshold
            # failures when we have the specific exception class available.
            if ValidationError is not None and isinstance(e, ValidationError):
                print(f"Ingest aborted for {a} due to validation threshold: {e}")
                return
            print(f"Validation step failed for {a}: {e}")

    # Calcula o retorno (usa coluna ajustada quando disponível, senão `close`)
    # Preferir o DataFrame `canonical` (já mapeado/validado) quando disponível.
    import src.retorno as rt

    target_df = canonical if "canonical" in locals() and canonical is not None else df

    price_candidates = ("Adj Close", "adj_close", "Close", "close")
    price_col = next((c for c in price_candidates if c in target_df.columns), None)
    if price_col is not None:
        target_df["Return"] = rt.r_log(
            target_df[price_col], target_df[price_col].shift(1)
        )
    else:
        target_df["Return"] = None

    # Save CSV for later stats (save the validated/mapped frame when possible)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target_df.to_csv(DATA_DIR / f"{a}.csv")


def _compute_and_print_stats(a: str) -> None:
    """Compute and print simple statistics for a saved asset CSV.

    Parameters
    ----------
    a : str
        Basename of the asset CSV to load (filename without directory).

    Behavior / side effects
    -----------------------
    - Reads the CSV file at `DATA_DIR/{a}.csv`.
    - Computes simple statistics from the `Return` column
      (sum, mean, std) and converts to annual metrics.
    - Prints a short summary to stdout.

    Expected input
    --------------
    The CSV is expected to contain a numeric column named `Return`.

    Errors
    ------
    If the CSV cannot be read the function prints an error message and
    returns early.

    Returns
    -------
    None
    """
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
