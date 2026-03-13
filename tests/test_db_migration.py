import sqlite3

import pytest

from src.db.schema import _ensure_schema


def _create_old_prices_table(conn: sqlite3.Connection) -> None:
    """Simulate a legacy schema where `date` is TEXT and no user_version."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE prices (
            ticker TEXT,
            date TEXT,
            source TEXT,
            raw_checksum TEXT,
            fetched_at TEXT,
            PRIMARY KEY(ticker, date)
        )
        """
    )
    conn.commit()


def test_ensure_schema_performs_migration(tmp_path):
    # start with an "old" database and confirm the migration runs once
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    _create_old_prices_table(conn)

    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    assert cur.fetchone()[0] == 0

    # running ensure_schema should bump user_version and convert affinity
    _ensure_schema(conn)

    cur.execute("PRAGMA user_version")
    assert cur.fetchone()[0] == 1
    cur.execute("PRAGMA table_info('prices')")
    info = {row[1]: (row[2] or "").upper() for row in cur.fetchall()}
    assert info.get("date") == "DATE"


def test_ensure_schema_skips_migration_when_version_set(monkeypatch):
    # When the database is already at user_version >= 1, the helper should
    # not be invoked again.
    conn = sqlite3.connect(":memory:")
    _ensure_schema(conn)

    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    assert cur.fetchone()[0] >= 1

    called = {"count": 0}

    def fake_migrate(c):
        called["count"] += 1

    # migration helper now lives in migrations module
    monkeypatch.setattr("src.db.migrations._migrate_prices_date_column", fake_migrate)

    # second call should skip the migration completely
    _ensure_schema(conn)
    assert called["count"] == 0


def test_apply_migrations_failure_preserves_cause(tmp_path):
    """A broken SQL file should raise MigrationError with original cause."""
    from src import db_migrator

    # create a migrations directory with invalid SQL
    migdir = tmp_path / "migrations"
    migdir.mkdir()
    bad = migdir / "0000_bad.sql"
    bad.write_text("THIS IS NOT SQL;")

    conn = sqlite3.connect(":memory:")
    with pytest.raises(db_migrator.MigrationError) as excinfo:
        db_migrator.apply_migrations(conn, migrations_dir=str(migdir))
    # original sqlite error should be chained as __cause__
    assert isinstance(excinfo.value.__cause__, Exception)
    assert "syntax error" in str(excinfo.value.__cause__).lower()
