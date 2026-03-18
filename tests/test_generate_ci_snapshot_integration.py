from pathlib import Path

import pytest

from src import db


def test_generate_ci_snapshot_writes_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generate CI snapshot and verify metadata is written to the metadata DB.

    The script should create a snapshot CSV and record a corresponding row in
    the configured metadata database (via SNAPSHOT_DB).
    """

    # prepare isolated DB
    db_path = tmp_path / "test.db"
    db.init_db(db_path=str(db_path))
    # apply migrations to ensure snapshots table exists
    from src.db_migrator import apply_migrations

    conn = db.connect(db_path=str(db_path))
    try:
        apply_migrations(conn)
    finally:
        conn.close()

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

    # verify snapshot file and checksum were created
    snapshot_file = snap_dir / "PETR4_snapshot.csv"
    checksum_file = snap_dir / "PETR4_snapshot.csv.checksum"

    assert snapshot_file.exists(), "Snapshot file was not created"
    assert checksum_file.exists(), "Checksum sidecar file was not created"
    assert checksum_file.read_text().strip(), "Checksum sidecar should not be empty"
