"""Optional pandera schema loader for the canonical CSVs.

This module defines a function `get_pandera_schema()` that returns a
`pandera` DataFrameSchema when `pandera` is installed, otherwise returns
None.

The canonical schema is persisted in `docs/schema.json` (authoritative
documentation). This keeps imports lazy so runtime does not fail when
pandera is not installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def get_pandera_schema(base_path: Optional[Path] = None):
    """Return a pandera DataFrameSchema if `pandera` is available.

    `base_path` allows callers to control where `docs/schema.json` is
    resolved from. When omitted the path is resolved relative to this
    module's parent directory so library and CLI usage behave
    consistently regardless of the current working directory.
    """
    try:
        import pandera as pa
        from pandera import Column, DataFrameSchema
    except Exception:
        return None

    if base_path is None:
        base_path = Path(__file__).resolve().parent.parent

    schema_path = base_path / "docs" / "schema.json"
    if not schema_path.exists():
        return None

    with schema_path.open("r", encoding="utf-8") as f:
        spec = json.load(f)
    cols = spec.get("columns", [])
    mapping = {}
    for c in cols:
        name = c.get("name")
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
    except Exception:
        return None
