import os

from tests import fixture_utils


def test_get_or_make_snapshot_dir_uses_env(tmp_path_factory, tmp_path, monkeypatch):
    # Prepare a directory path that does not yet exist
    env_dir = tmp_path / "ci_snapshots"
    monkeypatch.setenv("SNAPSHOT_DIR", str(env_dir))

    path = fixture_utils.get_or_make_snapshot_dir(
        os.environ.get("SNAPSHOT_DIR"), tmp_path_factory
    )

    assert os.path.isabs(path)
    assert os.path.abspath(str(env_dir)) == path
    assert os.path.isdir(path)


def test_get_or_make_snapshot_dir_creates_tmpdir(tmp_path_factory):
    path = fixture_utils.get_or_make_snapshot_dir(None, tmp_path_factory)
    assert os.path.isabs(path)
    assert os.path.exists(path)
