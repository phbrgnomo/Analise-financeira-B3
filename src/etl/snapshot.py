"""Snapshot exporter helpers.

Provides deterministic write for snapshot DataFrames using existing
serialization utilities so generated snapshots are stable across runs.
"""

from __future__ import annotations

import contextlib
import os
import re
from datetime import datetime
from pathlib import Path

from src.utils.checksums import serialize_df_bytes, sha256_bytes


def _snapshot_keep_latest() -> int:
    """Quantidade de snapshots recentes a manter por ticker."""
    raw = os.getenv("SNAPSHOTS_KEEP_LATEST", "1").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1
    return max(1, value)


# regex para reconhecer nomes de snapshot no formato esperado (ticker-timestamp.csv)
_SNAPSHOT_FILENAME_RE = re.compile(
    r"""
    ^(?P<ticker>[^-]+)              # ticker (anything except dash)
    -(?P<timestamp>\d{8}T\d{6})     # timestamp like 20240101T235959
    (?:-(?P<suffix>[^.]+))?         # optional suffix before extension
    \.csv$                          # .csv extension
    """,
    re.VERBOSE,
)


def _parse_snapshot_timestamp(path: Path) -> tuple[datetime | None, float]:
    """Tenta extrair o timestamp a partir do nome do arquivo.

    Retorna um par (timestamp, mtime) para uso na ordenação:
    - timestamp: datetime extraído do nome ou None se inválido
    - mtime: timestamp de modificação do arquivo (sempre definido)
    """
    mtime = path.stat().st_mtime
    match = _SNAPSHOT_FILENAME_RE.match(path.name)
    if not match:
        return None, mtime

    ts_str = match.group("timestamp")
    # Ajuste o formato caso o padrão de timestamp mude.
    try:
        ts = datetime.strptime(ts_str, "%Y%m%dT%H%M%S")
    except ValueError:
        return None, mtime
    return ts, mtime


def _prune_old_snapshots(out_path: Path) -> None:
    """Remove snapshots antigos mantendo apenas os N mais recentes.

    Apenas arquivos que seguem o padrão de nome esperado são considerados
    snapshots. Arquivos CSV fora do padrão são ignorados e nunca removidos por
    este processo.
    """
    keep_latest = _snapshot_keep_latest()
    prefix = out_path.name.split("-", 1)[0]
    pattern = f"{prefix}-*.csv"

    # Filtra apenas arquivos que batem com o padrão de snapshot esperado
    candidate_files = [
        path
        for path in out_path.parent.glob(pattern)
        if _SNAPSHOT_FILENAME_RE.match(path.name)
    ]

    # Ordena por timestamp extraído do nome (mais recente primeiro).
    # Arquivos sem timestamp válido caem para o final usando mtime como fallback.
    def _sort_key(path: Path) -> tuple[int, float, str]:
        ts, mtime = _parse_snapshot_timestamp(path)
        # Para ordenar em ordem decrescente, usamos um sinal negativo
        # quando há timestamp.
        if ts is not None:
            return (0, -ts.timestamp(), path.name)
        # Sem timestamp válido: ficam depois, ordenados por mtime decrescente.
        return (1, -mtime, path.name)

    files = sorted(candidate_files, key=_sort_key)

    for old_csv in files[keep_latest:]:
        # ignore common filesystem errors; let other exceptions bubble
        with contextlib.suppress(OSError):
            old_csv.unlink()
        old_checksum = old_csv.with_name(f"{old_csv.name}.checksum")
        with contextlib.suppress(OSError):
            old_checksum.unlink()


def write_snapshot(df, out_path: Path, *, set_permissions: bool = False) -> str:
    """Write a deterministic CSV snapshot and return its SHA256 hex digest.

    The function serializes the DataFrame using the project's canonical
    `serialize_df_bytes` helper (which sorts columns and index) and writes
    the bytes atomically. It also writes a companion `.checksum` file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = serialize_df_bytes(
        df,
        index=False,
        date_format="%Y-%m-%d",
        float_format="%.10g",
        na_rep="",
    )

    tmp = out_path.with_suffix(f"{out_path.suffix}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(str(tmp), str(out_path))

    checksum = sha256_bytes(data)
    checksum_path = out_path.with_name(f"{out_path.name}.checksum")
    checksum_path.write_text(checksum)
    _prune_old_snapshots(out_path)

    if set_permissions and hasattr(os, "chmod"):
        with contextlib.suppress(Exception):
            os.chmod(str(out_path), 0o640)
            os.chmod(str(checksum_path), 0o640)
    return checksum
