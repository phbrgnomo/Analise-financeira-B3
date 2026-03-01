"""Ponto de entrada da CLI Typer para o pipeline de análise financeira B3.

Define o objeto ``app`` do Typer, monta o sub-comando ``pipeline`` e expõe
comandos para ingestão, ETL e exportação de dados.

Use ``poetry run main --help`` para ver todos os comandos disponíveis.
"""

import os
from contextlib import suppress
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

# load any local .env file early so calls to os.getenv work below; this
# is a no-op when running in CI or when no file exists.
import src.db as _db
import src.retorno as _retorno
from src import metrics
from src.logging_config import configure_logging
from src.paths import DATA_DIR
from src.tickers import normalize_b3_ticker, ticker_variants

# load environment file now that imports are done
load_dotenv()

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

    app.add_typer(pipeline_module.app, name="pipeline")
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


def _compute_returns_for_ticker(
    ticker: str,
    start: Optional[str],
    end: Optional[str],
    dry_run: bool,
) -> int:
    """Executa cálculo de retornos para um ticker e retorna linhas geradas."""
    df = _retorno.compute_returns(ticker, start=start, end=end, dry_run=dry_run)
    if df is None or df.empty:
        return 0

    if dry_run:
        print(f"{ticker}: {len(df)} retornos calculados (dry-run)")
        print(df.head())
    else:
        print(f"{ticker}: {len(df)} retornos persistidos")

    return len(df)


def _as_bool(value: object) -> bool:
    """Converte valor potencialmente serializado pela CLI em booleano."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@app.command("run")
def run_cmd(
    ticker: Optional[str] = typer.Option(
        None,
        help=(
            "Ticker B3 específico (ex.: PETR4). Quando omitido, usa tickers "
            "padrão do projeto."
        ),
    ),
    provider: str = typer.Option(
        "yfinance",
        help="Nome do provider/adaptador a ser usado (ex.: yfinance)",
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

    effective_ticker = ticker or ticker_arg
    effective_provider = provider or provider_arg or "yfinance"
    effective_force_refresh = _as_bool(force_refresh)

    tickers: list[str]
    if effective_ticker is None:
        tickers = list(DEFAULT_TICKERS)
        print(f"Executando tickers padrão: {', '.join(tickers)}")
        print("Para ticker específico, execute: main run --ticker <ticker>")
    else:
        tickers = [_normalize_cli_ticker(effective_ticker)]

    ok = 0
    failed = 0
    for tk in tickers:
        result = ingest(
            ticker=tk,
            source=effective_provider,
            dry_run=False,
            force_refresh=effective_force_refresh,
        )
        if result.get("status") != "success":
            failed += 1
            print(
                f"Falha no ingest para {tk}: "
                f"{result.get('error_message', 'erro desconhecido')}"
            )
            continue

        rows = _compute_returns_for_ticker(tk, None, None, False)
        if rows == 0:
            print(f"{tk}: ingest concluído, mas sem retornos calculados")
            failed += 1
            continue
        ok += 1

    print(f"Resumo run: sucesso={ok}, falhas={failed}")


@app.command("compute-returns")
def compute_returns_cmd(
    ticker: Optional[str] = typer.Option(
        None,
        help=(
            "Ticker B3 para cálculo de retornos (ex.: PETR4, ITUB4, BOVA11). "
            "Quando omitido, calcula para todos os tickers existentes no banco."
        ),
    ),
    ticker_arg: Optional[str] = typer.Argument(None, hidden=True),
    start: Optional[str] = typer.Option(None, help="Data inicial YYYY-MM-DD"),
    end: Optional[str] = typer.Option(None, help="Data final YYYY-MM-DD"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Não persiste, apenas exibe resultados"
    ),
) -> None:
    """Calcula retornos diários para um ticker (ou todos) e persiste no DB."""
    effective_ticker = ticker or ticker_arg
    effective_dry_run = _as_bool(dry_run)

    targets: list[str]
    if effective_ticker is not None:
        normalized = _normalize_cli_ticker(effective_ticker)
        targets = [_db.resolve_existing_ticker(normalized) or normalized]
    else:
        targets = _db.list_price_tickers()
        if not targets:
            print("Nenhum ticker encontrado na tabela prices")
            return
        print(
            "--ticker não informado; calculando retornos para todos os "
            f"tickers no banco ({len(targets)})"
        )

    total_rows = 0
    processed = 0
    for target in targets:
        rows = _compute_returns_for_ticker(target, start, end, effective_dry_run)
        if rows == 0:
            print(f"{target}: nenhum retorno calculado")
            continue
        processed += 1
        total_rows += rows

    if processed == 0:
        print("Nenhum retorno calculado para os parâmetros fornecidos")
        return

    if effective_dry_run:
        print(f"Dry-run concluído: {total_rows} retornos calculados")
    else:
        print(
            "Cálculo concluído: "
            f"{total_rows} retornos persistidos para {processed} ticker(s)"
        )


@app.command("ingest-snapshot")
def ingest_snapshot_cmd(
    snapshot_path: str = typer.Argument(
        ..., help="Caminho do arquivo CSV local a ser importado para o banco"
    ),
    ticker: Optional[str] = typer.Option(
        None,
        help=(
            "Ticker B3 associado ao snapshot quando o CSV não traz coluna ticker"
        ),
    ),
    ticker_arg: Optional[str] = typer.Argument(None, hidden=True),
    force_refresh: bool = typer.Option(
        False, "--force-refresh", help="Ignora cache e processa novamente"
    ),
    ttl: Optional[int] = typer.Option(
        None, help="TTL do cache em segundos (usa SNAPSHOT_TTL se omitido)"
    ),
    cache_file: Optional[str] = typer.Option(
        None, help="Arquivo JSON usado para armazenar o cache"
    ),
) -> None:
    """Importa CSV local no SQLite com cache/checksum e ingestão incremental."""
    from src import ingest_cli

    effective_ticker = ticker or ticker_arg
    normalized_ticker = (
        _normalize_cli_ticker(effective_ticker)
        if effective_ticker
        else None
    )
    effective_force_refresh = _as_bool(force_refresh)
    try:
        result = ingest_cli.ingest_snapshot(
            snapshot_path,
            normalized_ticker,
            force_refresh=effective_force_refresh,
            ttl=ttl,
            cache_file=cache_file,
        )
    except Exception as e:
        print(f"Falha ao ingerir snapshot: {e}")
        raise

    print("Ingestão de snapshot concluída")
    print(result)


@app.command("export-csv")
def export_csv_cmd(
    ticker: str = typer.Option(
        ..., help="Ticker B3 para exportação (ex.: PETR4, BOVA11)"
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
        _, provider_variant = ticker_variants(normalized)
        resolved = provider_variant
        print(
            "Ticker não encontrado com nome base no banco; "
            f"tentando variante {provider_variant}"
        )

    df = _db.read_prices(resolved, start=start, end=end)
    if df.empty:
        print(f"Nenhum dado encontrado para {normalized}")
        return

    if output is None:
        output = DATA_DIR / f"{normalized}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index_label="date")
    print(f"CSV exportado com {len(df)} linha(s): {output}")


if __name__ == "__main__":
    with suppress(Exception):
        configure_logging()

    if os.getenv("PROMETHEUS_METRICS"):
        with suppress(Exception):
            port = int(os.getenv("PROMETHEUS_METRICS_PORT", "8000"))
            metrics.start_metrics_server(port)

    app()
