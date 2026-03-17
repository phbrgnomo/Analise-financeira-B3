"""Shared Typer option factories used throughout the CLI.

Centralizing common option definitions keeps help text consistent and
ensures changes (e.g. adding new flags or altering defaults) only need to
be made in one place.
"""

from __future__ import annotations

from typing import Any, Literal

import typer


def output_format_option(default: Literal["text", "json"] = "text") -> Any:
    """Return a reusable Typer Option for the `--format`/`-f` output selector."""

    return typer.Option(
        default,
        "--format",
        "-f",
        help="Formato de saída: text (padrão) ou json (para CI/integração).",
        case_sensitive=False,
    )
