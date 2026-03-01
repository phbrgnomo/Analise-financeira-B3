"""Resolução centralizada de caminhos importantes do projeto.

Expõe :func:`project_root` (raiz do repositório) e :data:`DATA_DIR`
(diretório de dados em runtime, padrão ``dados/``).  Usar estas referências
em vez de caminhos hardcoded garante comportamento correto tanto em
desenvolvimento local quanto em CI.
"""

from pathlib import Path


def project_root() -> Path:
    """Retorna o root do projeto (pasta que contém este arquivo em runtime)."""
    return Path(__file__).resolve().parents[1]


# Paths comuns usados pelo pipeline
SNAPSHOTS_DIR = Path("snapshots")
RAW_DIR = Path("raw")
METADATA_DIR = Path("metadata")
DATA_DIR = Path("dados")
