from pathlib import Path


def project_root() -> Path:
    """Retorna o root do projeto (pasta que contém este arquivo em runtime)."""
    return Path(__file__).resolve().parents[1]


# Paths comuns usados pelo pipeline
SNAPSHOTS_DIR = Path("snapshots")
RAW_DIR = Path("raw")
METADATA_DIR = Path("metadata")
DATA_DIR = Path("dados")
