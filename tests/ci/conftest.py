import pytest


@pytest.fixture(scope="session")
def snapshot_dir(tmp_path_factory):
    """Diretório temporário para salvar snapshots gerados nos testes CI.

    Usa um diretório temporário por execução de testes para evitar
    commitar artefatos no repositório. O CI fará upload desses arquivos
    como artifacts quando necessário.
    """
    d = tmp_path_factory.mktemp("snapshots")
    yield str(d)
