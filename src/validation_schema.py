"""Carregador opcional de esquema do pandera para os CSVs canônicos.

Este módulo é um wrapper fino que delega para
:func:`src.etl.mapper.load_canonical_schema_from_json`, a fonte canônica
de construção do DataFrameSchema do pandera desde a consolidação feita no
epic-1.

.. deprecated::
    Para novo código, importe :data:`src.etl.mapper.CanonicalSchema`
    diretamente. Esta função é mantida apenas para compatibilidade retroativa.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_pandera_schema(base_path: Optional[Path] = None):
    """Retorna um DataFrameSchema do pandera se ``pandera`` estiver disponível.

    Delega para :func:`src.etl.mapper.load_canonical_schema_from_json`, que é
    a fonte canônica de construção do schema no projeto.

    Parameters
    ----------
    base_path:
        Diretório raiz onde ``docs/schema.json`` será procurado.  Quando
        omitido usa o diretório pai do pacote (raiz do repositório).

    Returns
    -------
    DataFrameSchema | None
        Schema do pandera ou ``None`` se pandera não estiver disponível ou o
        arquivo de schema não for encontrado.
    """
    try:
        from src.etl.mapper import load_canonical_schema_from_json
    except ImportError:
        # pandera (ou mapper) não disponível: retorna None graciosamente
        return None

    if base_path is None:
        base_path = Path(__file__).resolve().parent.parent

    schema_path = base_path / "docs" / "schema.json"
    if not schema_path.exists():
        return None

    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        return load_canonical_schema_from_json(data)
    except Exception:
        logger.exception(
            "Falha ao carregar schema canônico do pandera: %s",
            schema_path,
        )
        return None
