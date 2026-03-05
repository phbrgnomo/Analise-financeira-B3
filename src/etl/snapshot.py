"""Snapshot exporter helpers.

Provides deterministic write for snapshot DataFrames using existing
serialization utilities so generated snapshots are stable across runs.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils.checksums import serialize_df_bytes, sha256_bytes

logger = logging.getLogger(__name__)


def snapshot_checksum(df: pd.DataFrame) -> str:
    """Compute the canonical SHA256 digest for a DataFrame snapshot.

    The implementation mirrors the serialization used by :func:`write_snapshot`.
    Having a dedicated helper avoids duplicating the formatting rules in the
    ingestion layer and ensures cache comparisons remain accurate if the
    serialization logic ever changes.
    """
    data = serialize_df_bytes(
        df,
        index=False,
        date_format="%Y-%m-%d",
        float_format="%.10g",
        na_rep="",
    )
    return sha256_bytes(data)


def _snapshot_keep_latest() -> int:
    """Quantidade de snapshots recentes a manter por ticker.

    This wrapper exists for backward compatibility with existing tests and
    callers.  The actual logic is delegated to
    :func:`src.ingest.config.get_snapshot_keep_latest` so that the same
    implementation is shared with the ingestion layer.
    """
    from src.ingest.config import get_snapshot_keep_latest

    return get_snapshot_keep_latest()


# regex para reconhecer nomes de snapshot no formato esperado
# o ticker B3 consiste em caracteres alfanuméricos maiúsculos e pode
# incluir um sufixo de provedor (por ex. ``.SA``), portanto restringimos o
# grupo para evitar que arquivos arbitrários coincidam acidentalmente.
_SNAPSHOT_FILENAME_RE = re.compile(
    r"""
    ^
    (?P<ticker>[A-Z0-9]+(?:\.[A-Z0-9]+)?)   # ticker maiúsculo com opcional ".SA"
    -(?P<timestamp>\d{8}T\d{6}Z?)          # timestamp yyyyMMddTHHMMSS, Z suffix allowed
    (?:-(?P<suffix>[^.]+))?                  # sufixo opcional antes da extensão
    \.csv$                                   # extensão .csv
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
    # strip trailing Z if present; the formatter used by
    # :func:`write_snapshot` appends a Z suffix to indicate UTC, but the
    # original parsing logic expected plain digits.  keeping both in sync
    # avoids mis-detecting otherwise valid filenames.
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1]
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

    Logs em nível ``DEBUG`` as ações de pruning para ajudar a diagnosticar
    possíveis exclusões inesperadas.  Se o nome do arquivo não casar com o
    padrão conhecido, um aviso em DEBUG também é emitido para esclarecer que
    nenhum pruning ocorrerá.
    """
    keep_latest = _snapshot_keep_latest()

    # Preferir extrair o ticker do próprio out_path usando a regex canônica.
    # Se o nome não casar com o padrão, caímos para o comportamento baseado
    # em prefixo (compatibilidade), mas sempre filtramos por ticker quando
    # possível para evitar deletar arquivos de tickers com prefixos comuns
    # (ex: PETR4 vs PETR4F).
    target_match = _SNAPSHOT_FILENAME_RE.match(out_path.name)
    if target_match:
        target_ticker = target_match.group("ticker")
        # procurar todos os CSVs que batem o padrão geral e então filtrar
        # apenas aqueles cujo ticker extraído coincide exatamente.
        candidate_files = []
        for path in out_path.parent.glob("*-*.csv"):
            m = _SNAPSHOT_FILENAME_RE.match(path.name)
            if not m:
                continue
            if m.group("ticker") != target_ticker:
                continue
            candidate_files.append(path)
    else:
        # nome fora do padrão: não sabemos o ticker, portanto não fazemos
        # pruning algum para evitar exclusões equivocadas. Isto é raro e
        # significa que o arquivo não segue o formato `ticker-timestamp.csv`.
        # logamos como WARNING para que seja visível em cenários onde o
        # comando é executado manualmente e nenhum filename válido foi usado.
        logger.warning(
            "_prune_old_snapshots: nome '%s' não combina com padrão, pulando pruning",
            out_path.name,
        )
        candidate_files = []

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

    if not candidate_files:
        logger.debug("_prune_old_snapshots: nenhuma snapshot candidata a pruning")

    for old_csv in files[keep_latest:]:
        logger.debug("_prune_old_snapshots: removendo snapshot antiga %s", old_csv.name)
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
        # only ignore OS-level permission errors; other exceptions should
        # propagate so callers can notice unexpected issues.
        with contextlib.suppress(OSError):
            os.chmod(str(out_path), 0o640)
            os.chmod(str(checksum_path), 0o640)
    return checksum
