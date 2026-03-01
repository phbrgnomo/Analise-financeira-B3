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

# apply CLI compatibility patch (monkeypatching) on import
with suppress(ImportError):
    import src.cli_compat  # noqa: F401

import typer

from src.adapters.factory import available_providers
from src.tickers import normalize_b3_ticker

app = typer.Typer()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


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
