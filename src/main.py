"""Ponto de entrada da CLI Typer para o pipeline de análise financeira B3.

Define o objeto ``app`` do Typer, monta o sub-comando ``pipeline`` e expõe
comandos para ingestão, ETL e exportação de dados.

Use ``poetry run main --help`` para ver todos os comandos disponíveis.
"""

import os
from contextlib import suppress
from pathlib import Path
from typing import Optional, TypedDict

import typer
from dotenv import load_dotenv

# load any local .env file early so calls to os.getenv work below; this
# is a no-op when running in CI or when no file exists.
load_dotenv()

import src.db as _db  # noqa: E402
import src.retorno as _retorno  # noqa: E402
from src import metrics  # noqa: E402
from src.logging_config import configure_logging  # noqa: E402
from src.paths import DATA_DIR  # noqa: E402
from src.tickers import normalize_b3_ticker, ticker_variants  # noqa: E402
from src.utils.conversions import as_bool  # noqa: E402

# compatibility shims have been extracted to ``src.cli_compat``; import
# here to ensure the patches are applied when the CLI is loaded.
with suppress(ImportError):
    import src.cli_compat  # noqa: F401 - import for side effects

app = typer.Typer()


def _load_default_tickers() -> tuple[str, ...]:
    """Carrega tickers padrão do ambiente, com fallback para defaults locais."""
    default = ("PETR4", "ITUB3", "BBDC4")
    raw = os.getenv("DEFAULT_TICKERS")
    if raw is None or not raw.strip():
        return default

    parsed = []
    for item in raw.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        try:
            parsed.append(normalize_b3_ticker(candidate))
        except ValueError:
            continue

    return tuple(parsed) if parsed else default


DEFAULT_TICKERS = _load_default_tickers()


try:
    from src import pipeline as pipeline_module

    # Expor o sub-app 'pipeline' com uma descrição para aparecer no help
    app.add_typer(
        pipeline_module.app,
        name="pipeline",
        help="Comandos do pipeline: operações de ingest e "
             "amostragem sem execução completa do ETL.",
    )
except ImportError as exc:
    import logging

    logging.getLogger(__name__).warning(
        "could not import pipeline subcommands: %s", exc
    )


def _normalize_cli_ticker(value: str) -> str:
    """Valida ticker no padrão B3 para entrada de CLI."""
    try:
        return normalize_b3_ticker(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc




class _ComputeResult(TypedDict):
    rows: int
    persisted: bool
    sample_df: object | None  # pandas.DataFrame or None



def _compute_returns_for_ticker(
    ticker: str,
    start: Optional[str],
    end: Optional[str],
    dry_run: bool,
) -> _ComputeResult:
    """Executa cálculo de retornos para um ticker e retorna metadados.

    O dicionário retornado contém os campos:
      * ``rows``: número de linhas no DataFrame final (0 caso vazio/None)
      * ``persisted``: ``True`` quando o resultado veio de uma escrita no DB
        (i.e. ``dry_run`` é ``False`` e havia pelo menos uma linha)
      * ``sample_df``: um pequeno subconjunto do DataFrame para uso em logs/CLI
        ou ``None`` se não houver dados.

    O objetivo é manter esta função livre de efeitos de apresentação; os
    comandos de nível superior decidem como (e se) exibem mensagens via
    ``typer.echo``.  Isso facilita o reuso da lógica em contextos não-CLI e
    torna os testes mais simples, já que podemos inspecionar o retorno sem
    capturar stdout.
    """
    df = _retorno.compute_returns(ticker, start=start, end=end, dry_run=dry_run)

    if df is None or df.empty:
        return {"rows": 0, "persisted": False, "sample_df": None}

    rows = len(df)
    persisted = not dry_run

    sample_df = df.head(5) if rows > 5 else df

    return {"rows": rows, "persisted": persisted, "sample_df": sample_df}




@app.command("run")
def run_cmd(
    ticker: str = typer.Option(
        "",
        help=(
            "Ticker B3 específico (ex.: PETR4). Quando omitido, usa tickers "
            "padrão do projeto."
        ),
        is_flag=False,
    ),
    provider: str = typer.Option(
        "yfinance",
        help="Nome do provider/adaptador a ser usado (ex.: yfinance)",
        is_flag=False,
    ),
    ticker_arg: Optional[str] = typer.Argument(None, hidden=True),
    provider_arg: Optional[str] = typer.Argument(None, hidden=True),
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        help="Força persistência ignorando decisões de cache do pipeline",
    ),
) -> None:
    """Executa fluxo ETL principal (ingestão + cálculo de retornos)."""
    from src.ingest.pipeline import ingest

    effective_ticker = ticker or ticker_arg or None
    effective_provider = provider or provider_arg or "yfinance"
    effective_force_refresh = as_bool(force_refresh)

    tickers: list[str]
    if effective_ticker is None:
        tickers = list(DEFAULT_TICKERS)
        typer.echo(f"Executando tickers padrão: {', '.join(tickers)}")
        typer.echo("Para ticker específico, execute: main run --ticker <ticker>")
    else:
        tickers = [_normalize_cli_ticker(effective_ticker)]

    ok = 0
    failed = 0
    warnings = 0
    for tk in tickers:
        result = ingest(
            ticker=tk,
            source=effective_provider,
            dry_run=False,
            force_refresh=effective_force_refresh,
        )
        if result.get("status") != "success":
            failed += 1
            typer.echo(
                f"Falha no ingest para {tk}: "
                f"{result.get('error_message', 'erro desconhecido')}"
            )
            continue

        compute_info = _compute_returns_for_ticker(tk, None, None, False)
        rows = compute_info.get("rows", 0)
        if rows == 0:
            # zero rows is not necessarily an error; could mean no new data
            warnings += 1
            typer.echo(
                f"{tk}: ingest concluído, mas sem retornos calculados (aviso)"
            )
            continue
        ok += 1

    summary = f"Resumo run: sucesso={ok}, falhas={failed}"
    if warnings:
        summary += f", avisos={warnings}"
    typer.echo(summary)


@app.command("compute-returns")
def compute_returns_cmd(
    ticker: str = typer.Option(
        "",
        help=(
            "Ticker B3 para cálculo de retornos (ex.: PETR4, ITUB4, BOVA11). "
            "Quando omitido, calcula para todos os tickers existentes no banco."
        ),
        is_flag=False,
    ),
    start: Optional[str] = typer.Option(
        None,
        help="Data inicial YYYY-MM-DD",
        is_flag=False,
    ),
    end: Optional[str] = typer.Option(
        None,
        help="Data final YYYY-MM-DD",
        is_flag=False,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Não persiste, apenas exibe resultados"
    ),
    ticker_arg: Optional[str] = typer.Argument(None, hidden=True),
) -> None:
    """Calcula retornos diários para um ticker (ou todos) e persiste no DB."""
    effective_ticker = ticker or ticker_arg or None
    effective_dry_run = as_bool(dry_run)

    # start/end may already be None when not provided
    # (previous logic converted empty strings, but Optional annotation
    # lets Typer produce None directly).

    targets: list[str]
    if effective_ticker is not None:
        normalized = _normalize_cli_ticker(effective_ticker)
        targets = [_db.resolve_existing_ticker(normalized) or normalized]
    else:
        targets = _db.list_price_tickers()
        if not targets:
            typer.echo("Nenhum ticker encontrado na tabela prices")
            return
        typer.echo(
            "--ticker não informado; calculando retornos para todos os "
            f"tickers no banco ({len(targets)})"
        )

    total_rows = 0
    processed = 0
    for target in targets:
        compute_info = _compute_returns_for_ticker(
            target, start, end, effective_dry_run
        )
        rows = compute_info.get("rows", 0)
        if rows == 0:
            typer.echo(f"{target}: nenhum retorno calculado")
            continue
        processed += 1
        total_rows += rows

    if processed == 0:
        typer.echo("Nenhum retorno calculado para os parâmetros fornecidos")
        return

    if effective_dry_run:
        typer.echo(f"Dry-run concluído: {total_rows} retornos calculados")
    else:
        typer.echo(
            "Cálculo concluído: "
            f"{total_rows} retornos persistidos para {processed} ticker(s)"
        )


@app.command("ingest-snapshot")
def ingest_snapshot_cmd(
    snapshot_path: str = typer.Argument(
        ..., help="Caminho do arquivo CSV local a ser importado para o banco"
    ),
    ticker: str = typer.Option(
        "",
        help=(
            "Ticker B3 associado ao snapshot quando o CSV não traz coluna ticker"
        ),
        is_flag=False,
    ),
    force_refresh: bool = typer.Option(
        False, "--force-refresh", help="Ignora cache e processa novamente"
    ),
    ttl: float = typer.Option(
        -1.0,
        help="TTL do cache em segundos (usa SNAPSHOT_TTL se omitido)",
        is_flag=False,
    ),
    cache_file: str = typer.Option(
        "", help="Arquivo JSON usado para armazenar o cache", is_flag=False
    ),
    ticker_arg: Optional[str] = typer.Argument(None, hidden=True),
) -> None:
    """Importa CSV local no SQLite com cache/checksum e ingestão incremental."""
    from src import ingest_cli

    effective_ticker = ticker or ticker_arg
    normalized_ticker = (
        _normalize_cli_ticker(effective_ticker) if effective_ticker else None
    )
    effective_force_refresh = as_bool(force_refresh)
    # translate CLI defaults back to None semantics for the helper
    ttl_arg = None if ttl < 0 else ttl
    cache_arg = cache_file or None
    try:
        result = ingest_cli.ingest_snapshot(
            snapshot_path,
            normalized_ticker,
            force_refresh=effective_force_refresh,
            ttl=ttl_arg,
            cache_file=cache_arg,
        )
    except Exception as e:
        typer.echo(f"Falha ao ingerir snapshot: {e}")
        raise

    typer.echo("Ingestão de snapshot concluída")
    typer.echo(result)


@app.command("export-csv")
def export_csv_cmd(
    # ticker is optional here to preserve the older CLI behaviour where the
    # value could be supplied as a positional argument (``ticker_arg``).  The
    # fallback logic below keeps the same semantics for programmatic callers
    # that may still pass the value positionally.
    ticker: Optional[str] = typer.Option(
        None,
        help=(
            "Ticker B3 para exportação (ex.: PETR4, BOVA11). "
            "Quando omitido, pode ser passado como argumento posicional "
            "oculto (compatibilidade)."
        ),
    ),
    ticker_arg: Optional[str] = typer.Argument(None, hidden=True),
    output: Optional[Path] = typer.Option(  # noqa: B008
        None,
        help="Caminho do CSV de saída (padrão: dados/<ticker>.csv)",
    ),
    start: Optional[str] = typer.Option(
        None,
        help="Data inicial YYYY-MM-DD",
    ),
    end: Optional[str] = typer.Option(
        None,
        help="Data final YYYY-MM-DD",
    ),
) -> None:
    """Exporta preços da base SQLite para CSV local."""
    effective_ticker = ticker or ticker_arg
    if effective_ticker is None:
        raise typer.BadParameter("ticker é obrigatório")

    normalized = _normalize_cli_ticker(effective_ticker)
    resolved = _db.resolve_existing_ticker(normalized)
    if resolved is None:
        # try the provider-specific variant (e.g. add .SA)
        _, provider_variant = ticker_variants(normalized)
        alt = _db.resolve_existing_ticker(provider_variant)
        if alt is not None:
            resolved = alt
            typer.echo(
                "Ticker não encontrado com nome base no banco; "
                f"usando variante {provider_variant}"
            )
        else:
            raise typer.BadParameter(
                f"Ticker {normalized} não encontrado no banco (base ou variante)"
            )

    df = _db.read_prices(resolved, start=start, end=end)
    if df.empty:
        typer.echo(f"Nenhum dado encontrado para {normalized}")
        return

    if output is None:
        output = DATA_DIR / f"{normalized}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index_label="date")
    typer.echo(f"CSV exportado com {len(df)} linha(s): {output}")


if __name__ == "__main__":
    with suppress(Exception):
        configure_logging()

    if os.getenv("PROMETHEUS_METRICS"):
        with suppress(Exception):
            port = int(os.getenv("PROMETHEUS_METRICS_PORT", "8000"))
            metrics.start_metrics_server(port)

    app()
