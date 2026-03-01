"""Ponto de entrada da CLI Typer para o pipeline de análise financeira B3.

Define o objeto ``app`` do Typer, monta o sub-comando ``pipeline`` e expõe
comandos para buscar, processar e calcular retornos de ativos listados na B3.

Use ``poetry run main --help`` para ver todos os comandos disponíveis.
"""

import os

# compatibility shims have been extracted to ``src.cli_compat``; import
# here to ensure the patches are applied when the CLI is loaded.
# (see story 1.3 follow‑up cleanup)
try:
    import src.cli_compat  # noqa: F401 - import for side effects
except ImportError:
    # not fatal; patching is best-effort
    pass

from datetime import date, timedelta
from typing import Optional

import typer

import src.db as _db
import src.retorno as _retorno
from src import metrics
from src.logging_config import configure_logging
from src.paths import DATA_DIR

# Instância principal da aplicação de linha de comando usando Typer
app = typer.Typer()

# mount sub-commands from other modules (kept small in this file)
try:
    from src import pipeline as pipeline_module

    app.add_typer(pipeline_module.app, name="pipeline")
except ImportError as exc:
    # pipeline module may not exist in some lightweight test environments; log
    # at WARNING level so misconfigurations are visible in normal runs.
    import logging

    logging.getLogger(__name__).warning(
        "could not import pipeline subcommands: %s", exc
    )

d_atual = date.today()


def _fetch_and_prepare_asset(
    a: str,
    d_in: str,
    d_fim: str,
    validation_tolerance: Optional[float],
    provider: str = "yfinance",
) -> None:
    """Executa ingestão via pipeline canônico e materializa CSV local para análises.

    O parâmetro ``validation_tolerance`` é mantido por compatibilidade de CLI,
    mas a validação fica centralizada no pipeline de ingestão.
    """
    from src.ingest.pipeline import ingest

    ticker = f"{a}.SA"
    if validation_tolerance is not None:
        print(
            "validation_tolerance informado; a validação é gerenciada "
            "internamente pelo pipeline."
        )

    result = ingest(ticker=ticker, source=provider, dry_run=False)
    if result.get("status") != "success":
        print(f"Falha no ingest para {ticker}: {result.get('error_message')}")
        return

    try:
        target_df = _db.read_prices(ticker)
    except Exception as e:
        print(f"Falha ao ler dados persistidos para {ticker}: {e}")
        return

    if target_df.empty:
        print(f"Nenhum dado disponível no banco para {ticker}")
        return

    # Calcula o retorno (usa coluna ajustada quando disponível, senão `close`).
    import src.retorno as rt

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
    retorno_anual = rt.conv_retorno(retorno_medio, rt.TRADING_DAYS)
    risco_anual = rt.conv_risco(risco, rt.TRADING_DAYS)

    print(f"\n--------{a}--------")
    print(f"Retorno total do período: {round((retorno_total * 100), 4)}%")
    print(f"Retorno médio ao dia: {round((retorno_medio * 100), 4)}%")
    print(f"Risco ao dia: {round((risco * 100), 4)}%")
    print(f"Retorno médio ao ano: {round((retorno_anual * 100), 4)}%")
    print(f"Risco ao ano: {round(risco_anual * 100, 4)}%")
    print(f"Coeficiente de variação(dia):{rt.coef_var(risco, retorno_medio)}")



@app.command("compute-returns")
def compute_returns_cmd(
    ticker: str = typer.Option(
        ..., help="Ticker para cálculo de retornos, ex: PETR4.SA"
    ),
    start: Optional[str] = typer.Option(
        None, help="Data inicial YYYY-MM-DD"
    ),
    end: Optional[str] = typer.Option(
        None, help="Data final YYYY-MM-DD"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Não persiste, apenas exibe resultados"
    ),
):
    """Calcula retornos diários para um ticker e persiste no DB (tabela returns)."""
    # Use public API: compute_returns will open/close DB connections itself
    df = _retorno.compute_returns(
        ticker, start=start, end=end, dry_run=dry_run
    )
    if df is None or df.empty:
        print("Nenhum retorno calculado para os parâmetros fornecidos")
        return
    print(f"Calculados {len(df)} retornos para {ticker}")
    if dry_run:
        print("Amostra do resultado (head):")
        print(df.head())
    else:
        print("Retornos persistidos no banco de dados")


@app.command("ingest-snapshot")
def ingest_snapshot_cmd(
    snapshot_path: str,
    ticker: Optional[str] = typer.Option(
        None, help="Ticker associado ao snapshot (se não estiver no CSV)"
    ),
    force_refresh: bool = typer.Option(
        False, "--force-refresh", help="Ignora cache e processa novamente"
    ),
    ttl: Optional[int] = typer.Option(
        None, help="TTL do cache em segundos (usa SNAPSHOT_TTL se omitido)"
    ),
    cache_file: Optional[str] = typer.Option(
        None, help="Arquivo JSON usado para armazenar o cache"
    ),
):
    """Ingesta um snapshot CSV com cache e ingestão incremental.

    A função delega para `src.ingest_cli.ingest_snapshot` e imprime o resultado.
    """
    from src import ingest_cli

    try:
        result = ingest_cli.ingest_snapshot(
            snapshot_path,
            ticker,
            force_refresh=force_refresh,
            ttl=ttl,
            cache_file=cache_file,
        )
    except Exception as e:
        print(f"Falha ao ingerir snapshot: {e}")
        raise

    print(result)


@app.command()
def main(  # noqa: C901
    validation_tolerance: Optional[float] = typer.Option(
        None, "--validation-tolerance", help="Tolerância de inválidas (ex: 0.10)"
    ),
    provider: str = typer.Option(
        "yfinance",
        "--provider",
        help="Nome do provider/adaptador a ser usado (ex: yfinance)",
    ),
):
    # importações locais para evitar exigir dependências apenas para `--help`

    import src.retorno as rt

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
        _fetch_and_prepare_asset(
            a, d_in, d_fim, validation_tolerance, provider=provider
        )  # noqa: E501

    for a in ativos:
        _compute_and_print_stats(a)

    # Calcula correlação entre os ativos
    newdf = rt.correlacao(ativos)
    print(newdf)


if __name__ == "__main__":
    # Configure structured logging only when executed as a program
    try:
        configure_logging()
    except Exception:
        # Best-effort: do not prevent CLI execution if logging setup fails
        pass

    # Optionally start Prometheus metrics server when requested via env var
    if os.getenv("PROMETHEUS_METRICS"):
        try:
            port = int(os.getenv("PROMETHEUS_METRICS_PORT", "8000"))
            metrics.start_metrics_server(port)
        except Exception:
            # Don't fail startup if metrics server can't start
            pass

    app()
