"""Checksum utilities.

Small helpers to compute SHA256 checksums for files and bytes.
"""

import hashlib
import logging
from pathlib import Path
from typing import Union

import pandas as pd

logger = logging.getLogger(__name__)


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

    The function may encounter situations where pandas operations cannot be
    performed (e.g. non-sortable columns); in those cases we log a *single*
    warning for the entire process using ``_non_deterministic_checksum_warned``
    so users aren't spammed by subsequent calls.
    """
    # declare global once for the entire function so subsequent assignments
    # aren't treated as local by the parser
    global _non_deterministic_checksum_warned

    df_to_serialize = df
    # Default to deterministic alphabetical column ordering unless caller
    # provided explicit `columns` ordering.  When any of our helpers fail we
    # scribble a warning; however such warnings tend to happen repeatedly in
    # loops so we guard with a global flag so the user only sees one message
    # per process.
    if columns is None:
        try:
            columns = sorted(df_to_serialize.columns)
        except (TypeError, ValueError):
            # Only catch errors we expect from attempting to sort non-sortable
            # column labels; other exceptions should propagate so the caller
            # can debug unexpected failures.
            if not _non_deterministic_checksum_warned:
                logger.warning(
                    "Não foi possível ordenar colunas do DataFrame; "
                    "usando ordem original (checksum pode ser "
                    "não-determinístico)"
                )
                _non_deterministic_checksum_warned = True
            columns = None

    if columns is not None:
        try:
            df_to_serialize = df_to_serialize.reindex(columns=columns)
        except Exception:
            if not _non_deterministic_checksum_warned:
                logger.warning(
                    "Não foi possível reindexar colunas do DataFrame; "
                    "usando cópia sem reordenação"
                )
                _non_deterministic_checksum_warned = True
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
        if not _non_deterministic_checksum_warned:
            logger.warning(
                "Falha ao ordenar DataFrame por índice; "
                "serializando sem sort (checksum pode ser "
                "não-determinístico)"
            )
            _non_deterministic_checksum_warned = True
        csv_str = df_to_serialize.to_csv(
            index=index,
            date_format=date_format,
            float_format=float_format,
            na_rep=na_rep,
        )

    return csv_str.encode("utf-8")



# module-level flags used by the warning guards above.  Older
# versions of the code tracked each failure case separately; new logic uses
# a single global guard so only the first warning is emitted.
_non_deterministic_checksum_warned = False
_warned_unsortable_columns = False  # kept for backward-compatibility tests
_warned_reindex_failure = False
_warned_sort_index_failure = False

__all__ = ["sha256_file", "sha256_bytes", "serialize_df_bytes"]
