import logging
from pathlib import Path

from src.etl import snapshot as snapshot_module


def _make_file(path: Path):
    path.write_text("")
    # ensure mtime order
    return path


def test_prune_old_snapshots_deletes_and_logs(tmp_path, caplog, monkeypatch):
    # keep only the most recent file
    monkeypatch.setattr(snapshot_module, "_snapshot_keep_latest", lambda: 1)
    # create three snapshots with increasing timestamps
    p1 = _make_file(tmp_path / "PETR4-20220101T000000.csv")
    p2 = _make_file(tmp_path / "PETR4-20220102T000000.csv")
    p3 = _make_file(tmp_path / "PETR4-20220103T000000.csv")

    caplog.set_level(logging.DEBUG)
    # call prune using the newest file path as in normal use
    snapshot_module._prune_old_snapshots(p3)

    # only the latest should remain
    assert not p1.exists(), "older snapshot should be deleted"
    assert not p2.exists(), "second snapshot should be deleted"
    assert p3.exists(), "most recent snapshot should be kept"

    # logging should mention removal of old snapshots
    assert "removendo snapshot antiga" in caplog.text


def test_prune_old_snapshots_pattern_mismatch_logs(tmp_path, caplog):
    # when the filename doesn't match the pattern we should warn and skip
    caplog.set_level(logging.WARNING)
    fake = tmp_path / "not-a-snapshot.csv"
    fake.write_text("")
    snapshot_module._prune_old_snapshots(fake)
    assert "não combina com padrão" in caplog.text
    # we only care that a warning was issued; debug details are optional.
