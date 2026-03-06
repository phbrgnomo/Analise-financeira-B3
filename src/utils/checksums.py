"""Checksum utilities.

Small helpers to compute SHA256 checksums for files and bytes.
"""

import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


# Guarda para garantir que emitimos no máximo um aviso relacionado a
# checksum por processo. Versões antigas rastreavam vários flags
# (_warned_unsortable_columns, _warned_reindex_failure,
# _warned_sort_index_failure), mas a lógica foi consolidada; mantemos um
# booleano único e expomos os nomes legados de forma sucinta nos testes para
# compatibilidade retroativa.
_non_deterministic_checksum_warned = False


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
    columns: Optional[List[str]] = None,
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
    # declarar global uma vez para toda a função para que atribuições
    # subsequentes não sejam tratadas como locais pelo interpretador
    global _non_deterministic_checksum_warned

    df_to_serialize = df
    # Por padrão usamos ordenação alfabética determinística das colunas
    # a menos que o chamador forneça `columns` explicitamente. Quando algum
    # de nossos auxiliares falha geramos um aviso; porém avisos assim tendem a
    # ocorrer repetidamente em loops, então protegemos com uma flag global
    # para que o usuário veja apenas uma mensagem por processo.
    if columns is None:
        try:
            columns = sorted(df_to_serialize.columns)
        except (TypeError, ValueError):
            # Capturamos apenas os erros que esperamos ao tentar ordenar
            # rótulos de coluna não ordenáveis; outras exceções devem
            # propagarem para que o chamador possa depurar falhas inesperadas.
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
        except (ValueError, TypeError, IndexError):
            # estes são os erros prováveis ao reindexar com rótulos de
            # coluna inválidos; outras exceções devem borbulhar para cima.
            if not _non_deterministic_checksum_warned:
                logger.warning(
                    "Não foi possível reindexar colunas do DataFrame; "
                    "usando cópia sem reordenação"
                )
                _non_deterministic_checksum_warned = True
            df_to_serialize = df_to_serialize.copy()

    # Ordenar pelo índice para tornar a saída determinística entre execuções
    try:
        csv_str = df_to_serialize.sort_index().to_csv(
            index=index,
            date_format=date_format,
            float_format=float_format,
            na_rep=na_rep,
        )
    except (TypeError, ValueError):
        # these are the common errors raised by sort_index when the index
        # contains unorderable or invalid values; other exceptions should
        # propagate normally.
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

__all__ = ["sha256_file", "sha256_bytes", "serialize_df_bytes"]
