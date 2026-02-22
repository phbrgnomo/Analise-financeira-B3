"""Checksum utilities.

Small helpers to compute SHA256 checksums for files and bytes.
"""

import hashlib
from pathlib import Path
from typing import Union

import pandas as pd


def sha256_file(path: Union[str, Path]) -> str:
    """Calculate SHA256 checksum for a file and return the hex digest.

    Args:
        path: Path-like or string to the file to hash.

    Returns:
        Hex digest string of the SHA256 hash.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return SHA256 hex digest for the given bytes."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def serialize_df_bytes(
    df: pd.DataFrame,
    *,
    index: bool = True,
    date_format: str = "%Y-%m-%dT%H:%M:%S",
    float_format: str = "%.10g",
    na_rep: str = "",
    columns: list | None = None,
) -> bytes:
    """Serialize a DataFrame to bytes deterministically.

    This helper is intended to produce a stable CSV bytes representation used
    both for writing raw files and for computing checksums so that different
    components generate the same digest when given the same DataFrame.
    """
    df_to_serialize = df
    # Default to deterministic alphabetical column ordering unless caller
    # provided explicit `columns` ordering.
    if columns is None:
        try:
            columns = sorted(df_to_serialize.columns)
        except Exception:
            columns = None

    if columns is not None:
        try:
            df_to_serialize = df_to_serialize.reindex(columns=columns)
        except Exception:
            df_to_serialize = df_to_serialize.copy()

    # Sort by index to make output deterministic across runs
    try:
        csv_str = df_to_serialize.sort_index().to_csv(
            index=index,
            date_format=date_format,
            float_format=float_format,
            na_rep=na_rep,
        )
    except Exception:
        csv_str = df_to_serialize.to_csv(
            index=index,
            date_format=date_format,
            float_format=float_format,
            na_rep=na_rep,
        )

    return csv_str.encode("utf-8")


__all__ = ["sha256_file", "sha256_bytes", "serialize_df_bytes"]
