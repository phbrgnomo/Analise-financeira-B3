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

app = typer.Typer()


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
