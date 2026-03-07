from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast, override

import pandas as pd
import typer

from src import db
from src.cli_feedback import CliFeedback
from src.paths import SNAPSHOTS_DIR
from src.retention import (
    archive_snapshots,
    delete_snapshots,
    find_purge_candidates,
    get_retention_days,
)

app = typer.Typer()

_PURGE_ARCHIVE_DIR_OPTION = typer.Option(
    None,
    "--archive-dir",
    help="Diretório para arquivar snapshots ao invés de deletar",
)


class _SnapshotExportFeedback(CliFeedback):
    @override
    def start(self, message: str) -> None:
        typer.echo(f"▶ {self.command_name}: {message}", err=True)

    @override
    def warn(self, message: str) -> None:
        typer.secho(f"⚠ {message}", fg=typer.colors.YELLOW, err=True)

    @override
    def success(self, message: str) -> None:
        typer.secho(f"✓ {message}", fg=typer.colors.GREEN, err=True)


def _resolve_snapshot_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return SNAPSHOTS_DIR / candidate


def _load_latest_snapshot(
    ticker: str,
    fb: _SnapshotExportFeedback,
) -> tuple[dict[str, object], pd.DataFrame]:
    snapshots = db.list_snapshots(ticker=ticker, archived=False)
    if not snapshots:
        fb.error(f"No snapshots found for ticker {ticker}")
        raise typer.Exit(code=1)

    metadata = snapshots[0]
    snapshot_path_raw = metadata.get("snapshot_path")
    if not isinstance(snapshot_path_raw, str) or not snapshot_path_raw.strip():
        fb.error(f"Snapshot metadata has no valid path for {ticker}")
        raise typer.Exit(code=1)

    snapshot_path = _resolve_snapshot_path(snapshot_path_raw)
    if not snapshot_path.exists():
        fb.error(f"Snapshot file not found: {snapshot_path}")
        raise typer.Exit(code=1)

    try:
        df = pd.read_csv(snapshot_path)
    except Exception as exc:
        fb.error(f"Failed to read snapshot file: {exc}")
        raise typer.Exit(code=1) from exc

    return metadata, df


def _serialize_export(
    requested_format: str,
    normalized_ticker: str,
    metadata: dict[str, object],
    df: pd.DataFrame,
    fb: _SnapshotExportFeedback,
) -> str:
    if requested_format == "csv":
        return df.to_csv(index=False)

    records_json_or_none = df.to_json(orient="records")
    if records_json_or_none is None:
        fb.error("Failed to serialize snapshot to JSON records")
        raise typer.Exit(code=1)

    data = cast(list[dict[str, Any]], json.loads(records_json_or_none))
    wrapper = {
        "ticker": normalized_ticker,
        "checksum": metadata.get("checksum"),
        "rows": len(data),
        "data": data,
    }
    return json.dumps(wrapper, ensure_ascii=False, indent=2) + "\n"


def _emit_export(content: str, output_path: Path | None) -> None:
    if output_path is None:
        _ = sys.stdout.write(content)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = output_path.write_text(content, encoding="utf-8")


def _show_candidates(
    feedback: CliFeedback,
    candidates: list[dict[str, object]],
    *,
    older_than: int,
) -> None:
    if not candidates:
        feedback.info(
            "Nenhum snapshot elegível para purge "
            f"(older-than={older_than} dias)."
        )
        return

    feedback.info(
        f"{len(candidates)} snapshot(s) elegível(eis) para purge "
        f"(older-than={older_than} dias):"
    )
    for row in candidates:
        feedback.info(
            "id="
            f"{row.get('id')} "
            f"ticker={row.get('ticker')} "
            f"created_at={row.get('created_at')} "
            f"size_bytes={row.get('size_bytes')} "
            f"path={row.get('path')}"
        )


@app.command("purge")
def purge_snapshots(
    older_than: int | None = typer.Option(
        None,
        "--older-than",
        help=(
            "Remove snapshots mais antigos que N dias "
            "(default: SNAPSHOT_RETENTION_DAYS ou 90)"
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Lista candidatos sem modificar estado",
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Executa exclusão/arquivamento real",
    ),
    archive_dir: Path | None = _PURGE_ARCHIVE_DIR_OPTION,
) -> None:
    feedback = CliFeedback("snapshots purge")

    if dry_run and confirm:
        feedback.error("--dry-run e --confirm não podem ser usados juntos")
        raise typer.Exit(code=1)

    effective_older_than = (
        older_than if older_than is not None else get_retention_days()
    )
    feedback.start(
        f"avaliando purge older-than={effective_older_than} dias "
        f"dry_run={dry_run} confirm={confirm}"
    )

    conn = db.connect()
    try:
        candidates = find_purge_candidates(conn, effective_older_than)
        _show_candidates(
            feedback,
            candidates,
            older_than=effective_older_than,
        )

        if dry_run:
            feedback.success("Dry-run concluído sem alterações")
            return

        if not confirm:
            feedback.warn("use --confirm para executar")
            return

        snapshot_ids = [
            candidate["id"]
            for candidate in candidates
            if "id" in candidate
        ]

        if archive_dir is not None:
            archived = archive_snapshots(
                conn,
                cast(list[int], snapshot_ids),
                archive_dir,
            )
            ok_count = sum(1 for row in archived if row.get("checksum_ok"))
            feedback.success(
                f"Arquivamento concluído: {len(archived)} snapshot(s), "
                f"checksums OK: {ok_count}"
            )
            return

        deleted = delete_snapshots(conn, cast(list[int], snapshot_ids))
        deleted_count = sum(1 for row in deleted if row.get("deleted"))
        feedback.success(
            f"Purge concluído: {len(deleted)} snapshot(s) processado(s), "
            f"arquivos removidos: {deleted_count}"
        )
    finally:
        conn.close()


@app.command("export")
def export_snapshot(
    ticker: str = typer.Option(
        ...,
        "--ticker",
        help="Ticker symbol (B3 format, e.g., PETR4)",
    ),
    format: str = typer.Option(
        "csv",
        "--format",
        help="Output format: csv or json",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        help="Output file path (default: stdout)",
    ),
) -> None:
    fb = _SnapshotExportFeedback("snapshots export")
    normalized_ticker = ticker.strip().upper()
    requested_format = format.strip().lower()

    if requested_format not in {"csv", "json"}:
        fb.error(f"Invalid format: {format}. Use 'csv' or 'json'.")
        raise typer.Exit(code=1)

    fb.start(f"Exporting snapshot for {normalized_ticker}")

    metadata, df = _load_latest_snapshot(normalized_ticker, fb)

    output_path = Path(output) if output else None

    try:
        content = _serialize_export(
            requested_format,
            normalized_ticker,
            metadata,
            df,
            fb,
        )
        _emit_export(content, output_path)
    except Exception as exc:
        fb.error(f"Failed to export snapshot: {exc}")
        raise typer.Exit(code=1) from exc

    target = str(output_path) if output_path else "stdout"
    fb.success(
        f"Snapshot exported ({requested_format}, {len(df)} rows, checksum="
        f"{metadata.get('checksum')}) to {target}"
    )
