"""Snapshot exporter helpers.

Provides deterministic write for snapshot DataFrames using existing
serialization utilities so generated snapshots are stable across runs.
"""
from __future__ import annotations

import os
from pathlib import Path

from src.utils.checksums import serialize_df_bytes, sha256_bytes


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

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(str(tmp), str(out_path))

    checksum = sha256_bytes(data)
    checksum_path = out_path.with_name(out_path.name + ".checksum")
    checksum_path.write_text(checksum)

    if set_permissions and hasattr(os, "chmod"):
        try:
            os.chmod(str(out_path), 0o640)
            os.chmod(str(checksum_path), 0o640)
        except Exception:
            pass

    return checksum
