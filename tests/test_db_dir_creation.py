
from src import db


def test_create_db_dir_and_file(tmp_path):
    db_file = tmp_path / "dados" / "data.db"
    parent = db_file.parent
    # ensure parent does not exist
    if parent.exists():
        # remove contents if any
        for p in parent.rglob("*"):
            if p.is_file():
                p.unlink()
        for p in sorted(parent.rglob("*"), reverse=True):
            try:
                if p.is_dir():
                    p.rmdir()
            except Exception:
                pass
        try:
            parent.rmdir()
        except Exception:
            pass

    assert not parent.exists()

    # Call the function which should create parent dir and the DB file
    db.create_tables_if_not_exists(db_path=str(db_file))

    assert parent.exists() and parent.is_dir()
    assert db_file.exists() and db_file.is_file()
