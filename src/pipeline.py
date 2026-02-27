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

# apply CLI compatibility patch (monkeypatching) on import
try:
    import src.cli_compat  # noqa: F401
except ImportError:
    pass

from enum import Enum

import typer


class Provider(str, Enum):
    yfinance = "yfinance"
    # other providers can be added here as needed

    def __str__(self) -> str:
        return self.value

app = typer.Typer()


@app.command("ingest")
def ingest_cmd(
    source: str = typer.Option(
        "yfinance",
        "--source",
        help="Provider adapter to use (choices defined by Provider enum)",
    ),
    ticker: str = typer.Argument(
        ..., help="Ticker to ingest, ex. PETR4.SA (positional)."
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

    try:
        src_name = Provider(source).value
    except ValueError as exc:
        raise typer.BadParameter(
            "unknown provider %r, choose from %s"
            % (source, ", ".join(e.value for e in Provider)),
        ) from exc
    exit_code = ingest_command(
        ticker, src_name, dry_run=dry_run, force_refresh=force_refresh
    )
    raise typer.Exit(code=exit_code)
