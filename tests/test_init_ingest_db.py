import pytest


def test_init_db_creates_default(tmp_path, monkeypatch):
    """Garante que o módulo utilize um `DATA_DIR` local de teste e que
    `init_db` crie o arquivo `data.db` no caminho fornecido.
    """
    # Assegura que o módulo use um DATA_DIR local para teste
    monkeypatch.setattr(
        "scripts.init_ingest_db.DATA_DIR",
        tmp_path / "dados",
        raising=False,
    )

    from scripts.init_ingest_db import init_db

    # Chama com caminho explícito (o valor default do módulo pode ter sido
    # vinculado anteriormente)
    db_path = tmp_path / "dados" / "data.db"
    init_db(db_path)
    assert db_path.exists()


def test_init_db_refuses_outside_and_allows_with_flag(tmp_path, monkeypatch):
    """Verifica comportamento de `init_db` quanto a caminhos externos.

    Confirma que, por padrão, `init_db` recusa inicializar um banco fora do
    `DATA_DIR` (lançando `ValueError`), e que ao chamar com
    `allow_external=True` a função permite criar o arquivo de banco fora do
    diretório protegido.
    """
    monkeypatch.setattr(
        "scripts.init_ingest_db.DATA_DIR",
        tmp_path / "dados",
        raising=False,
    )

    from scripts.init_ingest_db import init_db

    outside_db = tmp_path / "outside" / "data.db"

    # Default should refuse
    with pytest.raises(ValueError):
        init_db(outside_db)

    # With allow_external it should create the DB file
    init_db(outside_db, allow_external=True)
    assert outside_db.exists()
