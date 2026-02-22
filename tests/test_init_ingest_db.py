import pytest


def test_init_db_creates_default(tmp_path, monkeypatch):
    # Ensure the module uses a test-local DATA_DIR
    monkeypatch.setattr(
        "scripts.init_ingest_db.DATA_DIR",
        tmp_path / "dados",
        raising=False,
    )

    from scripts.init_ingest_db import init_db

    # Call with explicit path (module-level default may have been bound earlier)
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
