"""Snapshot exporter helpers.

Provides deterministic write for snapshot DataFrames using existing
serialization utilities so generated snapshots are stable across runs.
"""

from __future__ import annotations

import contextlib
import os
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


def _prune_old_snapshots(out_path: Path) -> None:
    """Remove snapshots antigos mantendo apenas os N mais recentes."""
    keep_latest = _snapshot_keep_latest()
    prefix = out_path.name.split("-", 1)[0]
    pattern = f"{prefix}-*.csv"
    files = sorted(
        out_path.parent.glob(pattern),
        key=lambda item: item.name,
        reverse=True,
    )
    for old_csv in files[keep_latest:]:
        with contextlib.suppress(Exception):
            old_csv.unlink()
        old_checksum = old_csv.with_name(f"{old_csv.name}.checksum")
        with contextlib.suppress(Exception):
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
