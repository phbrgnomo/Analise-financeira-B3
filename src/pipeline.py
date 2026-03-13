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

import json
import sqlite3
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

# apply CLI compatibility patch (monkeypatching) on import
with suppress(ImportError):
    import src.cli_compat  # noqa: F401

import pandas as pd
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


def _restore_snapshot_into_temp_db(
    snapshot_path: Path,
    temp_db_target: str,
    required_columns: list[str],
) -> tuple[dict[str, str], int]:
    """Load a CSV snapshot into a temporary SQLite database and run checks.

    Parameters
    ----------
    snapshot_path : Path
        Path to the snapshot CSV file to import.
    temp_db_target : str
        SQLite URI or path for the temporary database (':memory:' by default).
    required_columns : list[str]
        Column names that must be present in the snapshot for validation.

    Returns
    -------
    tuple[dict[str, str], int]
        A tuple containing a dictionary of check results and the number of rows
        restored.
    """
    checks: dict[str, str] = {
        "row_count": "fail",
        "columns_present": "fail",
        "checksum_match": "n/a",
        "sample_row_check": "fail",
    }
    rows_restored = 0
    required_set = set(required_columns)

    temp_conn = sqlite3.connect(temp_db_target)
    try:
        temp_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prices (
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                adj_close REAL,
                PRIMARY KEY (ticker, date)
            )
            """
        )

        df = pd.read_csv(snapshot_path)
        rows_restored = len(df)
        if "adj_close" not in df.columns and "close" in df.columns:
            df["adj_close"] = df["close"]
        checks["columns_present"] = (
            "pass" if required_set.issubset(set(df.columns)) else "fail"
        )
        if checks["columns_present"] == "fail":
            return checks, rows_restored

        restore_df = df[required_columns].copy()
        _ = restore_df.to_sql("prices", temp_conn, if_exists="append", index=False)
        temp_conn.commit()

        row_count_db = temp_conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        checks["row_count"] = "pass" if row_count_db == rows_restored else "fail"

        if rows_restored == 0:
            checks["sample_row_check"] = "fail"
            return checks, rows_restored

        first_row = restore_df.iloc[0]
        last_row = restore_df.iloc[-1]
        first_exists = (
            temp_conn.execute(
                "SELECT 1 FROM prices WHERE ticker = ? AND date = ?",
                (first_row["ticker"], str(first_row["date"])),
            ).fetchone()
            is not None
        )
        last_exists = (
            temp_conn.execute(
                "SELECT 1 FROM prices WHERE ticker = ? AND date = ?",
                (last_row["ticker"], str(last_row["date"])),
            ).fetchone()
            is not None
        )
        checks["sample_row_check"] = (
            "pass" if (first_exists and last_exists) else "fail"
        )
        return checks, rows_restored
    finally:
        temp_conn.close()


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
            "unknown provider %r, choose from %s" % (source, ", ".join(provs)),
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
        help=("CSV canônico de saída (padrão: dados/samples/<ticker>_sample.csv)"),
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
                "unknown provider %r, choose from %s" % (source, ", ".join(provs)),
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
    """Create a CSV snapshot of market data for a given ticker.

    Fetches price history for ``ticker`` (B3 format, e.g. ``PETR4``) from the
    database, optionally limiting the range with ``start``/``end`` dates in
    ``YYYY-MM-DD`` format.  The resulting snapshot file is written to
    ``output_dir`` (defaults to the configured ``SNAPSHOTS_DIR`` such as
    ``snapshots/``) and metadata is recorded in the database.  Returns ``None``
    but emits status via ``CliFeedback`` and may raise ``typer.Exit`` on errors.

    Parameters
    ----------
    ticker : str
        B3 ticker to snapshot.
    start : Optional[str]
        Inclusive start date filter (YYYY-MM-DD).
    end : Optional[str]
        Inclusive end date filter (YYYY-MM-DD).
    output_dir : Optional[str]
        Directory where the CSV file will be placed; created if missing.
    """
    """Generate a snapshot CSV for a given B3 ticker.

    This command reads historical price data for ``ticker`` (normalized to
    uppercase) from the database and writes a canonical snapshot file.  The
    optional ``start`` and ``end`` parameters filter the date range using
    ``YYYY-MM-DD`` strings.  ``output_dir`` specifies the directory where the
    CSV will be written; when omitted the default ``snapshots/`` directory is
    used (created if necessary).

    Parameters
    ----------
    ticker : str
        B3-formatted ticker symbol (e.g. ``PETR4``).
    start : Optional[str]
        Beginning of time window (inclusive) in ``YYYY-MM-DD`` format.
    end : Optional[str]
        End of time window (inclusive) in ``YYYY-MM-DD`` format.
    output_dir : Optional[str]
        Directory path for snapshot output; defaults to ``snapshots/``.

    Side effects
    ------------
    Writes a CSV file to the filesystem and records metadata in the
    snapshots database.  Emits status feedback on stderr via ``CliFeedback``.
    """
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

    _ = write_snapshot(df.reset_index(), out_path)

    # calculate once to avoid redundant filesystem stats
    size_bytes = out_path.stat().st_size
    metadata = {
        "ticker": normalized_ticker,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "snapshot_path": str(out_path.resolve()),
        "rows": len(df),
        "checksum": sha256_file(out_path),
        "size_bytes": size_bytes,
        "job_id": None,
    }
    db.record_snapshot_metadata(metadata, db_path=None)

    success_message = (
        f"Snapshot gerado: {out_path} ({len(df)} linhas, {size_bytes} bytes)"
    )
    fb.success(success_message)


@app.command("restore-verify")
def restore_verify_cmd(
    snapshot_path: Path = typer.Option(  # noqa: B008
        ..., "--snapshot-path", help="Path to snapshot CSV file"
    ),
    temp_db: Optional[Path] = typer.Option(  # noqa: B008
        None, "--temp-db", help="Temp DB path (default :memory:)"
    ),
) -> None:
    """Validate a snapshot file against its metadata in the database.

    Reads the CSV at ``snapshot_path`` and compares row counts, column
    presence, checksum, and sample rows with the corresponding metadata entry
    (optionally using a temporary database at ``temp_db`` instead of the
    default connection).  Prints JSON summary and uses exit codes to signal
    pass/warn/fail conditions.  Side effects are limited to reading files and
    optionally creating the temp DB.

    Parameters
    ----------
    snapshot_path : Path
        Filesystem path to the snapshot CSV to verify.
    temp_db : Optional[Path]
        When provided, a temporary SQLite database path is used for metadata
        lookups (default is ``:memory:``).
    """
    from src import db
    from src.db.snapshots import get_snapshot_by_path
    from src.utils.checksums import sha256_file

    fb = CliFeedback("pipeline restore-verify")
    fb.start("iniciando verificação de restauração")

    if not snapshot_path.exists():
        fb.error(f"Snapshot file not found: {snapshot_path}")
        raise typer.Exit(code=2)

    actual_checksum = sha256_file(snapshot_path)

    metadata_conn = db.connect(db_path=None)
    try:
        resolved_path = str(snapshot_path.resolve())
        metadata = get_snapshot_by_path(resolved_path, conn=metadata_conn)
        if metadata is None:
            metadata = get_snapshot_by_path(str(snapshot_path), conn=metadata_conn)
    finally:
        metadata_conn.close()

    required_columns = [
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adj_close",
    ]
    checks: dict[str, str] = {
        "row_count": "fail",
        "columns_present": "fail",
        "checksum_match": "n/a",
        "sample_row_check": "fail",
    }
    rows_restored = 0
    temp_db_target = str(temp_db) if temp_db is not None else ":memory:"
    try:
        checks, rows_restored = _restore_snapshot_into_temp_db(
            snapshot_path,
            temp_db_target,
            required_columns,
        )
    except (OSError, pd.errors.ParserError, sqlite3.DatabaseError, ValueError) as exc:
        fb.error(f"Falha ao restaurar snapshot: {exc}")
        report = {
            "job_id": str(uuid.uuid4()),
            "snapshot_path": str(snapshot_path),
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "checks": checks,
            "rows_restored": rows_restored,
            "overall_result": "FAIL",
        }
        fb.info(json.dumps(report, indent=2))
        raise typer.Exit(code=2) from exc

    if metadata and metadata.get("checksum"):
        checks["checksum_match"] = (
            "pass" if actual_checksum == metadata["checksum"] else "fail"
        )
    else:
        checks["checksum_match"] = "n/a"

    if (
        checks["columns_present"] == "fail"
        or checks["row_count"] == "fail"
        or checks["sample_row_check"] == "fail"
    ):
        overall_result = "FAIL"
        exit_code = 2
    elif checks["checksum_match"] == "fail":
        overall_result = "WARN"
        exit_code = 1
    else:
        overall_result = "PASS"
        exit_code = 0

    report = {
        "job_id": str(uuid.uuid4()),
        "snapshot_path": str(snapshot_path),
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "checks": checks,
        "rows_restored": rows_restored,
        "overall_result": overall_result,
    }
    fb.info(json.dumps(report, indent=2))

    if overall_result == "PASS":
        fb.success("Verificação concluída com sucesso")
    elif overall_result == "WARN":
        fb.warn("Verificação concluída com alerta de checksum")
    else:
        fb.error("Verificação falhou")

    raise typer.Exit(code=exit_code)
