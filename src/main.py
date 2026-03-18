"""Ponto de entrada da CLI Typer para o pipeline de análise financeira B3.

Define o objeto ``app`` do Typer, monta o sub-comando ``pipeline`` e expõe
comandos para ingestão, ETL e exportação de dados.

Use ``poetry run main --help`` para ver todos os comandos disponíveis.
"""

import logging
import os
import sqlite3
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional, TypedDict, cast

import typer

if TYPE_CHECKING:
    import pandas as pd
from dotenv import load_dotenv

import src.db as _db
import src.retorno as _retorno
from src import metrics
from src.cli_feedback import CliFeedback, StepHandle
from src.cli_options import output_format_option
from src.connectivity import test_provider_connection
from src.health import (
    compute_health_metrics,
    read_ingest_logs,
    resolve_ingest_log_path,
)
from src.logging_config import configure_logging
from src.paths import DATA_DIR
from src.tickers import normalize_b3_ticker, ticker_variants
from src.utils.conversions import as_bool

# load any local .env file early so calls to os.getenv work below; this
# is a no-op when running in CI or when no file exists.
load_dotenv()

# compatibility shims have been extracted to ``src.cli_compat``; import
# here to ensure the patches are applied when the CLI is loaded.
with suppress(ImportError):
    import src.cli_compat  # noqa: F401 - import for side effects

app = typer.Typer()


@app.callback(invoke_without_command=True)
def _main_callback(
    ctx: typer.Context,
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
    output_format: Literal["text", "json"] = output_format_option(),
    no_network: bool = typer.Option(
        False,
        "--no-network",
        help="Usa o provider dummy para execução sem acesso à rede (modo de teste/CI).",
        is_flag=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Executa o pipeline sem persistir dados no banco de dados.",
        is_flag=True,
    ),
    sample_tickers: str | None = typer.Option(
        None,
        "--sample-tickers",
        help=(
            "Ticker(s) para usar em vez da lista padrão. "
            "Use um arquivo (uma linha por ticker) ou uma lista separada por vírgulas."
        ),
    ),
    max_days: int | None = typer.Option(
        None,
        "--max-days",
        help="Limita o período de ingestão ao número de dias mais recentes. (Ex: 30)",
    ),
    run_notebook: bool = typer.Option(
        False,
        "--run-notebook",
        help="Executa o notebook de análise após o término do pipeline.",
        is_flag=True,
    ),
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        help="Força persistência ignorando decisões de cache do pipeline",
    ),
) -> None:
    """Callback que permite usar `main --ticker` como atalho para `main run`.

    Este callback é acionado quando nenhum subcomando é fornecido.
    """
    if ctx.invoked_subcommand is None:
        # Roda o comando principal de forma compatível com o comportamento
        # esperado pelo quickstart (sem precisar digitar "run").
        run_cmd(
            ticker=ticker,
            provider=provider,
            output_format=output_format,
            no_network=no_network,
            dry_run=dry_run,
            sample_tickers=sample_tickers,
            max_days=max_days,
            run_notebook=run_notebook,
            force_refresh=force_refresh,
        )


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
    from src import snapshot_cli as snapshot_cli_module

    # Expor o sub-app 'pipeline' com uma descrição para aparecer no help
    app.add_typer(
        pipeline_module.app,
        name="pipeline",
        help="Comandos do pipeline: operações de ingest e "
        "amostragem sem execução completa do ETL.",
    )
    app.add_typer(
        snapshot_cli_module.app,
        name="snapshots",
        help="Comandos para ingestão e geração de snapshots.",
    )
except ImportError as exc:
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
    sample_df: "pd.DataFrame | None"  # pandas.DataFrame or None


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


def _make_ticker_result(
    ticker: str,
    provider: str,
    ingest_result: dict[str, object],
    rows_returns: int,
    status: str,
) -> dict[str, object]:
    """Constrói a estrutura de resultado por ticker usada na saída JSON."""

    persist = ingest_result.get("persist") or {}
    if not isinstance(persist, dict):
        persist = {}
    persist = cast(dict[str, object], persist)

    return {
        "ticker": ticker,
        "provider": provider,
        "status": status,
        "rows_ingested": persist.get("rows_processed"),
        "rows_returns": rows_returns,
        "snapshot_path": persist.get("snapshot_path"),
        "snapshot_checksum": persist.get("checksum"),
        "error_message": ingest_result.get("error_message"),
    }


def _run_notebook(tickers: list[str], job_id: str) -> dict[str, object]:
    """Execute notebook em batch via papermill.

    This is an optional step invoked via `--run-notebook`.
    """

    feedback = CliFeedback("notebook")
    feedback.start("executando notebook de análise")

    input_nb = Path("examples") / "notebooks" / "returns-consumer.ipynb"
    output_dir = Path("reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_nb = output_dir / f"quickstart-{job_id}.ipynb"

    try:
        import papermill as pm  # type: ignore

        pm.execute_notebook(str(input_nb), str(output_nb))
        feedback.success(f"notebook concluído: {output_nb}")
        return {"status": "success", "output_notebook": str(output_nb)}
    except ImportError as exc:
        feedback.error(
            "papermill não está instalado. Instale com `pip install papermill`."
        )
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        feedback.error(f"falha ao executar notebook: {exc}")
        raise typer.Exit(code=2) from exc


def _run_one_ticker(  # noqa: C901
    ticker: str,
    provider: str,
    dry_run: bool,
    force_refresh: bool,
    start: str | None,
    end: str | None,
    feedback: CliFeedback | None,
) -> tuple[dict[str, object], str]:
    """Run ingest + returns for a single ticker.

    Returns a tuple `(result_dict, status)` where `status` is one of
    ``success``, ``warning`` or ``failure``.
    """

    from src.ingest.pipeline import ingest

    ingest_step: StepHandle | None = None
    if feedback:
        feedback.item(ticker, 1, 1)
        ingest_step = feedback.start_step(
            "ingestão",
            detail=(
                f"ticker={ticker} | force_refresh={force_refresh} "
                f"| dry_run={dry_run} | start={start or '-'} | end={end or '-'}"
            ),
        )

    ingest_result = ingest(
        ticker=ticker,
        source=provider,
        dry_run=dry_run,
        force_refresh=force_refresh,
        start=start,
        end=end,
    )

    if ingest_result.get("status") != "success":
        if feedback and ingest_step is not None:
            feedback.finish_step(
                ingest_step,
                status="error",
                detail=ingest_result.get("error_message", "erro desconhecido"),
            )
        return (
            _make_ticker_result(ticker, provider, ingest_result, 0, "failure"),
            "failure",
        )

    if feedback and ingest_step is not None:
        ingest_detail = []
        if ingest_result.get("duration"):
            ingest_detail.append(f"total={ingest_result['duration']}")

        persist = ingest_result.get("persist")
        if isinstance(persist, dict):
            if persist_reason := persist.get("reason"):
                ingest_detail.append(f"reason={persist_reason}")

        feedback.finish_step(
            ingest_step,
            detail=" | ".join(ingest_detail) if ingest_detail else None,
        )

    returns_step: StepHandle | None = None
    if feedback:
        returns_step = feedback.start_step("cálculo de retornos", detail=ticker)

    compute_info = _compute_returns_for_ticker(ticker, start, end, dry_run)
    rows = compute_info.get("rows", 0)

    if rows == 0:
        if feedback and returns_step is not None:
            feedback.finish_step(
                returns_step,
                status="warning",
                detail="nenhum retorno calculado",
            )
        return (
            _make_ticker_result(ticker, provider, ingest_result, 0, "warning"),
            "warning",
        )

    if feedback and returns_step is not None:
        feedback.finish_step(
            returns_step,
            detail=f"{rows} retorno(s) persistidos",
        )

    return (
        _make_ticker_result(ticker, provider, ingest_result, rows, "success"),
        "success",
    )


def _parse_sample_tickers(value: str | None) -> list[str] | None:
    """Parse a ticker list from CLI option, supporting file or comma-separated.

    The value can be either a path to a file containing one ticker per line,
    or a comma-separated list of tickers.
    """

    if not value:
        return None

    path = Path(value)
    if path.exists():
        lines = [line.strip() for line in path.read_text().splitlines()]
        tickers = [line for line in lines if line and not line.startswith("#")]
    else:
        tickers = [t.strip() for t in value.split(",") if t.strip()]

    if not tickers:
        return None

    return tickers


def _prepare_run_context(
    ticker: str,
    provider: str,
    output_json: bool,
    no_network: bool,
    ticker_arg: Optional[str],
    provider_arg: Optional[str],
    sample_tickers: list[str] | None = None,
) -> tuple[list[str], CliFeedback | None, str]:
    """Prepara tickers, provider efetivo e objeto de feedback para o comando run."""

    # Some Typer callback invocations (notably when the root callback is used)
    # will pass an ``ArgInfo`` object instead of a plain string when the
    # positional argument is omitted.  This happens because Typer / Click keeps
    # the argument metadata around for help generation and can inject it into
    # the callback call during validation.
    #
    # We normalize the value here to avoid crashing (e.g. ``AttributeError``)
    # when we later treat it as a ticker string.
    def _normalize_ticker_param(value: object) -> str | None:
        if isinstance(value, str):
            return value
        return None

    effective_ticker = (
        _normalize_ticker_param(ticker) or _normalize_ticker_param(ticker_arg) or None
    )

    effective_provider = provider or provider_arg or "yfinance"
    if no_network:
        effective_provider = "dummy"

    feedback = None if output_json else CliFeedback("executar")

    if effective_ticker is not None:
        tickers = [_normalize_cli_ticker(effective_ticker)]
        if feedback:
            feedback.start(
                f"processando ticker={tickers[0]} com provider={effective_provider}"
            )
        return tickers, feedback, effective_provider

    if sample_tickers:
        # honor explicit sample list before falling back to defaults
        tickers = [_normalize_cli_ticker(t) for t in sample_tickers]
        if feedback:
            feedback.start(
                f"processando tickers de amostra com provider={effective_provider}"
            )
            feedback.info(f"Tickers: {', '.join(tickers)}")
        return tickers, feedback, effective_provider

    tickers = list(DEFAULT_TICKERS)
    if feedback:
        feedback.start(f"processando tickers padrão com provider={effective_provider}")
        feedback.info(f"Tickers: {', '.join(tickers)}")
        feedback.info("Para ticker específico, execute: main --ticker <ticker>")

    return tickers, feedback, effective_provider


def _aggregate_run_results(
    results: list[dict[str, object]],
) -> tuple[str, int, int, int, int]:
    """Retorna status agregado, código de saída e contagens dos resultados."""

    success_count = sum(r.get("status") == "success" for r in results)
    warning_count = sum(r.get("status") == "warning" for r in results)
    failure_count = sum(r.get("status") == "failure" for r in results)

    status = "success"
    if failure_count:
        status = "failure"
    elif warning_count:
        status = "warning"

    if status == "success":
        exit_code = 0
    elif status == "warning":
        exit_code = 1
    else:
        exit_code = 2

    return status, exit_code, success_count, warning_count, failure_count


@app.command("run")
def run_cmd(  # noqa: C901
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
    output_format: Literal["text", "json"] = output_format_option(),
    no_network: bool = typer.Option(
        False,
        "--no-network",
        help="Usa o provider dummy para execução sem acesso à rede (modo de teste/CI).",
        is_flag=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Executa o pipeline sem persistir dados no banco de dados.",
        is_flag=True,
    ),
    sample_tickers: str | None = typer.Option(
        None,
        "--sample-tickers",
        help=(
            "Ticker(s) para usar em vez da lista padrão."
            " Pode ser arquivo (uma linha por ticker) ou lista separada por vírgulas."
        ),
    ),
    max_days: int | None = typer.Option(
        None,
        "--max-days",
        help="Limita o período de ingestão aos últimos N dias. (ex: --max-days 30)",
    ),
    run_notebook: bool = typer.Option(
        False,
        "--run-notebook",
        help="Executa o notebook de análise após o término do pipeline.",
        is_flag=True,
    ),
    ticker_arg: Optional[str] = typer.Argument(None, hidden=True),
    provider_arg: Optional[str] = typer.Argument(None, hidden=True),
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        help="Força persistência ignorando decisões de cache do pipeline",
    ),
) -> None:
    """Executa fluxo ETL principal (ingestão + cálculo de retornos).

    Saída de código:
      * 0 - sucesso (todos os tickers processados com status success)
      * 1 - warning (algum ticker retornou status warning)
      * 2 - erro (falha em algum ticker ou em steps críticos como notebook)
    """

    output_json = output_format == "json"
    effective_force_refresh = as_bool(force_refresh)

    # Determine a time window to pass to the adapter.
    start_date: str | None = None
    end_date: str | None = None
    if max_days is not None:
        from src.ingest.pipeline import _resolve_sample_window

        start_date, end_date = _resolve_sample_window(max_days, None, None)

    tickers, feedback, effective_provider = _prepare_run_context(
        ticker=ticker,
        provider=provider,
        output_json=output_json,
        no_network=no_network,
        ticker_arg=ticker_arg,
        provider_arg=provider_arg,
        sample_tickers=_parse_sample_tickers(sample_tickers),
    )

    job_id = str(uuid.uuid4())
    run_started = time.monotonic()

    results: list[dict[str, object]] = []
    for _idx, tk in enumerate(tickers, start=1):
        result, _status = _run_one_ticker(
            ticker=tk,
            provider=effective_provider,
            dry_run=dry_run,
            force_refresh=effective_force_refresh,
            start=start_date,
            end=end_date,
            feedback=feedback,
        )
        results.append(result)

    summary_status, exit_code, success_count, warning_count, failure_count = (
        _aggregate_run_results(results)
    )
    duration_sec = time.monotonic() - run_started
    summary = {
        "status": summary_status,
        "job_id": job_id,
        "duration_sec": duration_sec,
        "tickers": results,
    }

    if run_notebook:
        notebook_results = _run_notebook(tickers, job_id)
        summary["notebook"] = notebook_results

    if output_json:
        CliFeedback("executar").json_output(summary)
        raise typer.Exit(code=exit_code)

    if feedback is None:
        # Fallback when feedback is unexpectedly None: print summary to stdout.
        typer.echo(
            f"job_id={job_id} | duration_sec={duration_sec:.2f} | "
            f"sucesso={success_count} falhas={failure_count}"
            + (f" avisos={warning_count}" if warning_count else "")
        )
    else:
        feedback.summary(
            f"job_id={job_id} | duration_sec={duration_sec:.2f} | "
            f"sucesso={success_count} falhas={failure_count}"
            + (f" avisos={warning_count}" if warning_count else "")
        )

    # Print per-ticker summaries including snapshot path and rows.
    if feedback:
        for r in results:
            snapshot = r.get("snapshot_path") or "-"
            rows = r.get("rows_ingested") or 0
            feedback.info(f"ticker={r.get('ticker')} snapshot={snapshot} rows={rows}")

    raise typer.Exit(code=exit_code)


@app.command("metrics")
def metrics_cmd(
    output_format: Literal["text", "json"] = output_format_option(),
    ingest_log_path: Optional[str] = typer.Option(
        None,
        "--ingest-log-path",
        help=(
            "Caminho para o arquivo ingest_logs.jsonl "
            "(default: metadata/ingest_logs.jsonl)."
        ),
    ),
    threshold: str = typer.Option(
        os.getenv("INGEST_LAG_THRESHOLD", "86400"),
        "--threshold",
        help="Valor em segundos para o limite de ingest lag (default 86400).",
    ),
) -> None:
    """Exibe métricas de health do pipeline."""

    path = resolve_ingest_log_path(ingest_log_path)
    logs = read_ingest_logs(path)

    try:
        threshold_seconds = int(threshold)
    except Exception:
        logging.getLogger(__name__).warning(
            "invalid INGEST_LAG_THRESHOLD=%r, using default 86400", threshold
        )
        threshold_seconds = 86400

    summary = compute_health_metrics(logs, threshold_seconds)

    feedback = CliFeedback("metrics")

    if output_format == "json":
        feedback.json_output(summary)
        raise typer.Exit(code=0)

    feedback.info(f"status: {summary['status']}")
    feedback.info(f"ingest_lag_seconds: {summary['metrics']['ingest_lag_seconds']}")
    feedback.info(f"errors_last_24h: {summary['metrics']['errors_last_24h']}")
    feedback.info(f"jobs_last_24h: {summary['metrics']['jobs_last_24h']}")
    avg = summary["metrics"].get("avg_latency_seconds")
    if avg is None:
        feedback.info("avg_latency_seconds: null")
    else:
        feedback.info(f"avg_latency_seconds: {avg:.3f}")


@app.command("test-conn")
def test_conn_cmd(
    provider: str = typer.Option(
        "yfinance",
        help="Nome do provider/adaptador a ser usado (ex.: yfinance)",
        is_flag=False,
    ),
    output_format: Literal["text", "json"] = output_format_option(),
) -> None:
    """Verifica conectividade com um provider/adaptador."""

    result = test_provider_connection(provider)

    feedback = CliFeedback("test-conn")

    if output_format == "json":
        feedback.json_output(result)
        raise typer.Exit(code=0 if result.get("status") == "success" else 2)

    if result.get("status") == "success":
        latency = result.get("latency_ms")
        if isinstance(latency, (int, float)):
            feedback.success(f"OK ({latency / 1000:.3f}s)")
        else:
            feedback.success("OK")
    else:
        error_msg = result.get("error") or "erro desconhecido"
        feedback.error(error_msg)
        raise typer.Exit(code=2)


def _gather_compute_targets(
    effective_ticker: Optional[str],
    start: Optional[str],
    end: Optional[str],
    effective_dry_run: bool,
    feedback: CliFeedback,
) -> Optional[list[str]]:
    """Resolve os tickers alvo para compute-returns.

    Retorna lista de tickers ou None para indicar que o comando deve
    encerrar sem processar nada (feedback já terá sido emitido).
    """
    if effective_ticker is not None:
        normalized = _normalize_cli_ticker(effective_ticker)
        try:
            resolved = _db.resolve_existing_ticker(normalized)
        except sqlite3.OperationalError as e:
            logging.getLogger(__name__).error(
                "erro ao resolver ticker existente %s: %s", normalized, e
            )
            resolved = None
        targets = [resolved or normalized]
        feedback.start(
            f"ticker={targets[0]} | dry_run={effective_dry_run} | "
            f"start={start or '-'} | end={end or '-'}"
        )
        return targets

    try:
        targets = _db.list_price_tickers()
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "no such table" in msg and "prices" in msg:
            return _no_targets_feedback(feedback, "Nenhuma tabela prices encontrada")
        raise

    if not targets:
        return _no_targets_feedback(
            feedback, "Nenhum ticker encontrado na tabela prices"
        )
    feedback.start(
        f"processando todos os tickers do banco ({len(targets)}) | "
        f"dry_run={effective_dry_run}"
    )
    return targets


def _no_targets_feedback(feedback: CliFeedback, message: str) -> None:
    """Emit feedback when no targets are found in the database.

    Starts the feedback session and emits a warning message. Returns None to
    indicate the caller should abort processing.
    """
    feedback.start("processando todos os tickers do banco")
    feedback.warn(message)
    return None


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
    feedback = CliFeedback("compute-returns")
    effective_ticker = ticker or ticker_arg or None
    effective_dry_run = as_bool(dry_run)

    targets = _gather_compute_targets(
        effective_ticker, start, end, effective_dry_run, feedback
    )
    if not targets:
        return

    total_rows = 0
    processed = 0
    for idx, target in enumerate(targets, start=1):
        feedback.item(target, idx, len(targets))
        step = feedback.start_step(
            "cálculo de retornos",
            detail=f"start={start or '-'} | end={end or '-'}",
        )
        compute_info = _compute_returns_for_ticker(
            target, start, end, effective_dry_run
        )
        rows = compute_info.get("rows", 0)
        if rows == 0:
            feedback.finish_step(
                step,
                status="warning",
                detail="nenhum retorno calculado",
            )
            continue

        processed += 1
        total_rows += rows
        mode = "calculados" if effective_dry_run else "persistidos"
        feedback.finish_step(step, detail=f"{rows} retorno(s) {mode}")

    if processed == 0:
        feedback.warn("Nenhum retorno calculado para os parâmetros fornecidos")
        return

    if effective_dry_run:
        feedback.summary(f"Dry-run concluído: {total_rows} retornos calculados")
    else:
        feedback.summary(
            "Cálculo concluído: "
            f"{total_rows} retornos persistidos para {processed} ticker(s)"
        )


# `ingest-snapshot` foi removido: usar `main snapshots ingest`.
# Atualize scripts e documentação que referenciem o comando antigo.


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
    feedback = CliFeedback("export-csv")
    effective_ticker = ticker or ticker_arg
    if effective_ticker is None:
        raise typer.BadParameter("ticker é obrigatório")

    normalized = _normalize_cli_ticker(effective_ticker)
    feedback.start(
        f"ticker={normalized} | output={output or DATA_DIR / f'{normalized}.csv'} | "
        f"start={start or '-'} | end={end or '-'}"
    )
    try:
        resolved = _db.resolve_existing_ticker(normalized)
    except sqlite3.OperationalError as e:
        # This can happen if the database schema is missing (e.g. migrations not run).
        logging.getLogger(__name__).error(
            "erro ao resolver ticker existente %s: %s", normalized, e
        )
        feedback.error(
            "Erro de acesso ao banco de dados; verifique se o esquema está "
            "inicializado e execute as migrações"
        )
        return

    if resolved is None:
        # try the provider-specific variant (e.g. add .SA)
        _, provider_variant = ticker_variants(normalized)
        alt = _db.resolve_existing_ticker(provider_variant)
        if alt is None:
            raise typer.BadParameter(
                f"Ticker {normalized} não encontrado no banco (base ou variante)"
            )

        resolved = alt
        feedback.warn(
            "Ticker não encontrado com nome base no banco; "
            f"usando variante {provider_variant}"
        )
    read_step = feedback.start_step("leitura no banco", detail=resolved)
    df = _db.read_prices(resolved, start=start, end=end)
    if df.empty:
        feedback.finish_step(
            read_step,
            status="warning",
            detail="nenhum dado encontrado",
        )
        feedback.warn(f"Nenhum dado encontrado para {normalized}")
        return
    feedback.finish_step(read_step, detail=f"{len(df)} linha(s) lidas")

    if output is None:
        output = DATA_DIR / f"{normalized}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_step = feedback.start_step("gravação do CSV", detail=str(output))
    df.to_csv(output, index_label="date")
    feedback.finish_step(write_step, detail=f"{len(df)} linha(s) gravadas")
    feedback.summary(f"CSV exportado com {len(df)} linha(s): {output}")


if __name__ == "__main__":
    # configuração de logging deve ser tentada, mas qualquer erro deve
    # ser reportado em vez de silenciosamente ignorado.
    try:
        configure_logging()
    except Exception as e:  # pragma: no cover - very unlikely, but safe
        # usar logger disponível, mesmo que básico
        logging.getLogger(__name__).exception("falha ao configurar logging: %s", e)

    if os.getenv("PROMETHEUS_METRICS"):
        raw_port = os.getenv("PROMETHEUS_METRICS_PORT", "8000")
        try:
            port = int(raw_port)
        except ValueError:
            logging.getLogger(__name__).error(
                "porta de métricas inválida %r; ignorando inicialização",
                raw_port,
            )
        else:
            try:
                metrics.start_metrics_server(port)
            except Exception as e:  # include OSError and others
                logging.getLogger(__name__).exception(
                    "falha ao iniciar servidor de métricas na porta %s: %s",
                    port,
                    e,
                )

    app()
