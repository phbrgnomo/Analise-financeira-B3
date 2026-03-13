from pathlib import Path

from src import db


def test_generate_ci_snapshot_writes_metadata(tmp_path, monkeypatch):
    # prepare isolated DB
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    # apply migrations to ensure snapshots table exists
    from src.db_migrator import apply_migrations

    db.init_db(db_path=str(db_path))
    apply_migrations(db.connect(db_path=str(db_path)))

    # ensure the script uses our temp DB by overriding the default path
    from src.db import connection as conn_module

    monkeypatch.setattr(conn_module, "DEFAULT_DB_PATH", str(db_path))

    # prepare snapshot dir
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SNAPSHOT_DIR", str(snap_dir))
    # ensure script writes metadata into our test DB
    monkeypatch.setenv("SNAPSHOT_DB", str(db_path))

    # run the script in-process so monkeypatches affect it
    import importlib
    import sys

    # ensure fresh import so our monkeypatch of DEFAULT_DB_PATH is used
    if "scripts.generate_ci_snapshot" in sys.modules:
        del sys.modules["scripts.generate_ci_snapshot"]

    gen = importlib.import_module("scripts.generate_ci_snapshot")
    rc = gen.main()
    assert rc == 0

    # verify metadata row exists in our test DB
    conn2 = db.connect(db_path=str(db_path))
    cur = conn2.cursor()
    cur.execute(
        "SELECT id, ticker, snapshot_path, checksum FROM snapshots "
        "WHERE ticker = ? LIMIT 1",
        ("PETR4",),
    )
    row = cur.fetchone()
    assert row is not None, "No snapshot metadata recorded"
    _id, ticker, snapshot_path, checksum = row
    assert ticker == "PETR4"
    sp = Path(snapshot_path)
    if not sp.is_absolute():
        sp = snap_dir / sp
    assert sp.exists()
    assert isinstance(checksum, str) and len(checksum) == 64

    conn2.close()
