"""Utilitários reutilizáveis para feedback visual na CLI.

O objetivo deste módulo é centralizar mensagens de progresso, duração e
resultado para comandos Typer/Click do projeto. A implementação usa apenas
``typer.echo``/``typer.secho`` para manter zero dependências extras e poder
ser reutilizada por qualquer comando em ``src.main`` ou sub-apps.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import typer


@dataclass(frozen=True)
class StepHandle:
    """Representa uma etapa em andamento da CLI."""

    name: str
    started_at: float
    detail: str | None = None


def format_duration(seconds: float) -> str:
    """Formata uma duração em texto curto e legível."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, remaining = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {remaining:.1f}s"
    hours, remaining_minutes = divmod(int(minutes), 60)
    return f"{hours}h {remaining_minutes}m"


class CliFeedback:
    """Helper simples para exibir progresso, etapas e resumos na CLI."""

    def __init__(self, command_name: str) -> None:
        """Inicializa o helper com o nome lógico do comando."""
        self.command_name = command_name
        self.started_at = time.monotonic()

    def start(self, message: str) -> None:
        """Exibe a mensagem inicial do comando."""
        typer.echo(f"▶ {self.command_name}: {message}")

    def item(self, label: str, index: int, total: int) -> None:
        """Exibe o item atual de um processamento em lote."""
        typer.echo(f"→ [{index}/{total}] {label}")

    def info(self, message: str) -> None:
        """Exibe uma mensagem informativa."""
        typer.echo(f"• {message}")

    def warn(self, message: str) -> None:
        """Exibe uma mensagem de aviso."""
        typer.secho(f"⚠ {message}", fg=typer.colors.YELLOW)

    def error(self, message: str) -> None:
        """Exibe uma mensagem de erro em stderr."""
        typer.secho(f"✗ {message}", fg=typer.colors.RED, err=True)

    def success(self, message: str) -> None:
        """Exibe uma mensagem de sucesso."""
        typer.secho(f"✓ {message}", fg=typer.colors.GREEN)

    def start_step(self, name: str, detail: str | None = None) -> StepHandle:
        """Marca o início de uma etapa e retorna um handle para finalização."""
        suffix = f" — {detail}" if detail else ""
        typer.echo(f"… {name}{suffix}")
        return StepHandle(name=name, started_at=time.monotonic(), detail=detail)

    def finish_step(
        self,
        handle: StepHandle,
        *,
        status: str = "success",
        detail: str | None = None,
    ) -> None:
        """Finaliza uma etapa com status, detalhe e duração formatada."""
        elapsed = format_duration(time.monotonic() - handle.started_at)
        suffix = f" — {detail}" if detail else ""

        if status == "error":
            typer.secho(
                f"✗ {handle.name} ({elapsed}){suffix}",
                fg=typer.colors.RED,
                err=True,
            )
            return
        if status == "warning":
            typer.secho(
                f"⚠ {handle.name} ({elapsed}){suffix}",
                fg=typer.colors.YELLOW,
            )
            return
        if status == "skip":
            typer.echo(f"↷ {handle.name} ({elapsed}){suffix}")
            return

        typer.secho(
            f"✓ {handle.name} ({elapsed}){suffix}",
            fg=typer.colors.GREEN,
        )

    def summary(self, message: str) -> None:
        """Exibe o resumo final com a duração total do comando."""
        elapsed = format_duration(time.monotonic() - self.started_at)
        typer.echo(f"■ {message} ({elapsed})")
