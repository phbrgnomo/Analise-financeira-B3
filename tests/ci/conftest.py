import os

import pytest


@pytest.fixture(scope="session")
def snapshot_dir():
    """Diretório temporário para salvar snapshots gerados nos testes CI."""
    d = os.path.join(os.getcwd(), "snapshots_test")
    os.makedirs(d, exist_ok=True)
    yield d
    # keep snapshots for inspection; do not remove automatically
