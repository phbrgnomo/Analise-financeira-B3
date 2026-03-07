import sqlite3

import pytest

from src.db_migrator import MigrationError, apply_migrations


def _make_dir_with_file(tmp_path, name, contents):
    d = tmp_path / "migrations"
    d.mkdir()
    f = d / name
    f.write_text(contents)
    return str(d)


def test_apply_migrations_no_dir(tmp_path):
    """Nonexistent directory should be a no-op and not raise."""
    conn = sqlite3.connect(":memory:")
    # should not raise
    apply_migrations(conn, migrations_dir=str(tmp_path / "doesnotexist"))
    # the table should not exist either
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    )
    assert cur.fetchall() == []


def test_apply_migrations_success(tmp_path):
    conn = sqlite3.connect(":memory:")
    migrations_dir = _make_dir_with_file(
        tmp_path, "0000_init.sql", "CREATE TABLE foo(id INTEGER PRIMARY KEY);"
    )
    apply_migrations(conn, migrations_dir=migrations_dir)
    # table foo should exist and migration recorded
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='foo'")
    assert cur.fetchone() is not None
    cur.execute("SELECT id FROM schema_migrations")
    assert cur.fetchone()[0] == "0000_init.sql"


def test_apply_migrations_failure(tmp_path):
    conn = sqlite3.connect(":memory:")
    # write a migration that has invalid SQL
    migrations_dir = _make_dir_with_file(tmp_path, "0001_bad.sql", "INVALID SQL;;")
    with pytest.raises(MigrationError) as excinfo:
        apply_migrations(conn, migrations_dir=migrations_dir)
    # ensure original sqlite3 error is available as __cause__
    assert isinstance(excinfo.value.__cause__, sqlite3.Error)
    # table schema_migrations should still exist although we rolled back
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE name='schema_migrations'")
    assert cur.fetchone() is not None
