"""Shared Typer option factories used throughout the CLI.

Centralizing common option definitions keeps help text consistent and
ensures changes (e.g. adding new flags or altering defaults) only need to
be made in one place.
"""

from __future__ import annotations

from typing import Any, Literal

import typer


def output_format_option(default: Literal["text", "json"] = "text") -> Any:
    """Return a reusable Typer Option for the `--format`/`-f` output selector.

    The option value is validated and normalized to lowercase here so
    downstream code can compare directly to the canonical values
    ("text" / "json").
    """

    def _normalize_output_format(ctx, param, value):
        if value is None:
            return None
        val = str(value).strip().lower()
        if val not in ("text", "json"):
            raise typer.BadParameter("Formato inválido, use 'text' ou 'json'")
        return val

    return typer.Option(
        default,
        "--format",
        "-f",
        help="Formato de saída: text (padrão) ou json (para CI/integração).",
        callback=_normalize_output_format,
    )
