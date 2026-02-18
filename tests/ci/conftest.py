import pytest


@pytest.fixture(scope="session")
def snapshot_dir(tmp_path_factory) -> str:
    """Diretório temporário (como string) para salvar snapshots gerados nos testes CI.

    Usa um diretório temporário por execução de testes para evitar
    commitar artefatos no repositório. O CI fará upload desses arquivos
    como artifacts quando necessário.
    Retorna o caminho do diretório temporário como ``str``.
    """
    import os

    # If CI or caller provided SNAPSHOT_DIR, use it (create if not exists)
    env_path = os.environ.get("SNAPSHOT_DIR")
    if env_path:
        os.makedirs(env_path, exist_ok=True)
        yield os.path.abspath(env_path)
    else:
        d = tmp_path_factory.mktemp("snapshots")
        yield str(d)
