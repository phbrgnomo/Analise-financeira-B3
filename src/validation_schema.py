"""Carregador opcional de esquema do pandera para os CSVs canônicos.

Este módulo define a função `get_pandera_schema()` que retorna um
`pandera` DataFrameSchema quando `pandera` está instalado, caso contrário
retorna None.

O esquema canônico é persistido em `docs/schema.json` (documentação
autoritativa). Mantemos os imports de forma "lazy" para que o tempo de
execução não falhe quando o pacote `pandera` não estiver instalado.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_pandera_schema(base_path: Optional[Path] = None):  # noqa: C901
    """Retorna um DataFrameSchema do pandera se `pandera` estiver disponível.

    `base_path` permite que o chamador controle onde `docs/schema.json`
    será resolvido. Quando omitido, o caminho é resolvido em relação ao
    diretório pai deste módulo, de forma que o uso em biblioteca e CLI
    se comporte de maneira consistente independentemente do diretório de
    trabalho corrente.
    """
    try:
        import pandera as pa
        from pandera import Column, DataFrameSchema
    except ImportError:
        # Dependência opcional não instalada: o chamador pode tratar isso como
        # "sem esquema" e prosseguir sem validação via pandera
        return None

    if base_path is None:
        base_path = Path(__file__).resolve().parent.parent

    schema_path = base_path / "docs" / "schema.json"
    if not schema_path.exists():
        return None

    try:
        with schema_path.open("r", encoding="utf-8") as f:
            spec = json.load(f)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in pandera schema file: %s", schema_path)
        raise

    cols = spec.get("columns", [])
    mapping = {}
    for c in cols:
        # Validate column spec shape and required 'name' key
        if not isinstance(c, dict):
            logger.error("Invalid column spec (not an object): %r", c)
            raise ValueError(f"Invalid column spec: {c!r}")

        name = c.get("name")
        if not isinstance(name, str) or name == "":
            logger.error("Missing or invalid 'name' in column spec: %r", c)
            raise ValueError(f"Invalid column specification, missing 'name': {c!r}")

        t = c.get("type")
        nullable = c.get("nullable", True)
        if t in ("float", "number"):
            mapping[name] = Column(pa.Float, nullable=nullable)
        elif t in ("int", "integer"):
            mapping[name] = Column(pa.Int, nullable=nullable)
        elif t in ("string", "str"):
            mapping[name] = Column(pa.String, nullable=nullable)
        elif t in ("date", "datetime"):
            mapping[name] = Column(pa.DateTime, nullable=nullable)
        else:
            mapping[name] = Column(pa.Object, nullable=nullable)

    try:
        return DataFrameSchema(mapping)
    except Exception as err:
        # Some schema construction errors are expected when the JSON is
        # malformed for pandera; treat those as "no schema" (return None)
        # while logging unexpected errors and re-raising them.
        SchemaError = None
        if "pa" in locals():
            SchemaError = getattr(getattr(pa, "errors", None), "SchemaError", None)

        is_expected_err = isinstance(err, (ValueError, TypeError))
        if SchemaError and isinstance(err, SchemaError):
            is_expected_err = True

        if is_expected_err:
            logger.warning(
                "Failed to construct pandera DataFrameSchema from %s: %s",
                schema_path,
                err,
            )
            return None

        logger.exception(
            "Unexpected error while constructing pandera DataFrameSchema from %s: %s",
            schema_path,
            err,
        )
        raise
