"""Top-level pipeline CLI commands.

The repository previously placed all CLI logic under ``src.main``.  Story
1.3 drove the creation of a dedicated ``pipeline.ingest`` command; a simple
Typer sub-app is exposed here so that ``src.main`` can mount it without
becoming excessively large.

The commands defined in this module are intentionally thin wrappers around
logic in ``src.ingest.pipeline`` to support easier unit testing and reuse by
non-CLI callers (e.g. notebooks, API layers).
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

# apply CLI compatibility patch (monkeypatching) on import
with suppress(ImportError):
    import src.cli_compat  # noqa: F401

import typer

from src.adapters.factory import available_providers
from src.cli_feedback import CliFeedback
from src.paths import SNAPSHOTS_DIR
from src.tickers import normalize_b3_ticker
from src.utils.conversions import as_bool as _as_bool

app = typer.Typer()


def _normalize_cli_ticker(value: str) -> str:
    try:
        return normalize_b3_ticker(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("ingest")
def ingest_cmd(
    source: str = typer.Option(
        "yfinance",
        "--source",
        help=f"Provider adapter to use (choices: {', '.join(available_providers())})",
    ),
    ticker: str = typer.Argument(
        ..., help="Ticker B3 para ingestão, ex.: PETR4, MGLU3, BOVA11"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Fetch and map but do not write any data"
    ),
    force_refresh: bool = typer.Option(
        False, "--force-refresh", help="Ignore any cache when persisting"
    ),
) -> None:
    """Orchestrate a minimal end-to-end ingest using the configured adapters.

    ``ticker`` is a required positional parameter; Click requires options to
    appear before arguments when intermixed, so callers should place
    ``--source`` (and other flags) ahead of the ticker value.
    The provider name is validated against the ``Provider`` enum to offer a
    helpful error message.
    """
    from src.ingest.pipeline import ingest_command

    # provider validation is dynamic based on registered adapters
    provs = available_providers()
    # build lowercase map -> canonical name for stable normalization
    prov_map = {p.lower(): p for p in provs}
    src_key = source.lower()
    if src_key not in prov_map:
        raise typer.BadParameter(
            "unknown provider %r, choose from %s"
            % (source, ", ".join(provs)),
        )
    src_name = prov_map[src_key]
    try:
        normalized_ticker = normalize_b3_ticker(ticker)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    exit_code = ingest_command(
        normalized_ticker,
        src_name,
        dry_run=_as_bool(dry_run),
        force_refresh=_as_bool(force_refresh),
    )
    raise typer.Exit(code=exit_code)


@app.command("pull-sample")
def pull_sample_cmd(
    source: str = typer.Option(
        "",
        "--source",
        help=(
            "Provider adapter to use. Quando omitido, mostra fontes "
            "disponíveis e usa yfinance."
        ),
    ),
    ticker: str = typer.Argument(
        ..., help="Ticker B3 para amostra visual, ex.: PETR4, VALE3, BOVA11"
    ),
    days: int = typer.Option(
        10,
        "--days",
        min=1,
        help="Janela em dias quando --start não for informado",
    ),
    start: str | None = typer.Option(None, "--start", help="Data inicial YYYY-MM-DD"),
    end: str | None = typer.Option(None, "--end", help="Data final YYYY-MM-DD"),
    output: str | None = typer.Option(
        None,
        "--output",
        help=(
            "CSV canônico de saída (padrão: dados/samples/<ticker>_sample.csv)"
        ),
    ),
) -> None:
    """Gera artefatos raw/canônico de amostra via adapter sem persistir no DB."""
    from src.ingest.pipeline import pull_sample_command

    provs = available_providers()
    prov_map = {p.lower(): p for p in provs}

    raw_source = source.strip()
    if not raw_source:
        typer.echo(f"Fontes disponíveis: {', '.join(provs)}")
        src_name = "yfinance"
        typer.echo(f"Usando fonte padrão: {src_name}")
    else:
        src_key = raw_source.lower()
        if src_key not in prov_map:
            raise typer.BadParameter(
                "unknown provider %r, choose from %s"
                % (source, ", ".join(provs)),
            )
        src_name = prov_map[src_key]

    try:
        normalized_ticker = normalize_b3_ticker(ticker)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    exit_code = pull_sample_command(
        normalized_ticker,
        src_name,
        days=days,
        start=start,
        end=end,
        output=output,
    )
    raise typer.Exit(code=exit_code)


@app.command("snapshot")
def snapshot(
    ticker: str = typer.Option(..., "--ticker", help="Ticker B3, ex.: PETR4"),
    start: Optional[str] = typer.Option(
        None,
        "--start",
        help="Data inicial YYYY-MM-DD",
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        help="Data final YYYY-MM-DD",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        help="Diretório de saída (padrão: snapshots/)",
    ),
) -> None:
    from src import db
    from src.etl.snapshot import write_snapshot
    from src.utils.checksums import sha256_file

    fb = CliFeedback("pipeline snapshot")
    fb.start("iniciando geração de snapshot")

    try:
        normalized_ticker = _normalize_cli_ticker(ticker)
    except typer.BadParameter as exc:
        fb.error(str(exc))
        raise typer.Exit(code=1) from exc

    df = db.read_prices(normalized_ticker, start=start, end=end, db_path=None)

    if df.empty:
        fb.error(f"Nenhum dado encontrado para {normalized_ticker}")
        raise typer.Exit(code=1)

    out_dir = Path(output_dir) if output_dir else SNAPSHOTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{normalized_ticker}_snapshot.csv"

    _ = write_snapshot(df, out_path)

    metadata = {
        "ticker": normalized_ticker,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "snapshot_path": str(out_path.resolve()),
        "rows": len(df),
        "checksum": sha256_file(out_path),
        "size_bytes": out_path.stat().st_size,
        "job_id": None,
    }
    db.record_snapshot_metadata(metadata, db_path=None)

    size_bytes = out_path.stat().st_size
    success_message = (
        f"Snapshot gerado: {out_path} "
        f"({len(df)} linhas, {size_bytes} bytes)"
    )
    fb.success(success_message)
