from pathlib import Path

from src.ingest.snapshot_ingest import _check_cache_hit


def test_cache_hit_logs_on_invalid_processed_at(caplog):
    """Malformed timestamp in cache entry should log a warning and be a cache miss."""
    caplog.set_level("WARNING")
    cache = {"/tmp/foo.csv": {"sha256": "foo", "processed_at": "not-a-timestamp"}}

    result = _check_cache_hit(
        cache_file=cache,
        snapshot_path=Path("/tmp/foo.csv"),
        checksum="foo",
        ttl=100,
        force=False,
        ticker="TICK",
    )
    assert result is None
    assert "invalid" in caplog.text.lower()
    assert "not-a-timestamp" in caplog.text


def test_cache_hit_handles_non_string_processed_at(caplog):
    """Non-string processed_at values are treated as cache misses."""
    caplog.set_level("WARNING")
    cache = {"/tmp/foo.csv": {"sha256": "foo", "processed_at": 123}}

    result = _check_cache_hit(
        cache_file=cache,
        snapshot_path=Path("/tmp/foo.csv"),
        checksum="foo",
        ttl=100,
        force=False,
        ticker="TICK",
    )
    assert result is None
    assert "invalid" in caplog.text.lower()


def test_sanitized_filename_and_path(tmp_path, monkeypatch):
    """Ticker values with separators should be cleaned and file kept inside dir."""
    import pandas as pd

    import src.ingest.snapshot_ingest as si

    # stub out writing to avoid creating real files on disk
    monkeypatch.setattr("src.etl.snapshot.write_snapshot", lambda df, path: "deadbeef")

    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir()
    df = pd.DataFrame({"x": [1, 2]})

    # ticker contains traversal and illegal chars
    bad = "../foo/bar.TICK?"
    sha, out_path = si._write_snapshot_file(df, bad, snap_dir)
    assert sha == "deadbeef"
    # output path must be inside snapshot directory
    assert out_path.resolve().is_relative_to(snap_dir.resolve())
    # filename should have no path separators and illegal chars replaced
    assert ".." not in out_path.name
    assert "/" not in out_path.name
    assert "?" not in out_path.name
    assert "foo_bar_TICK_" in out_path.name

    # even a ticker that looks like a path should be safely mapped
    evil = "..\\evil"  # backslash on windows-like input
    sha2, out2 = si._write_snapshot_file(df, evil, snap_dir)
    assert sha2 == "deadbeef"
    assert out2.resolve().is_relative_to(snap_dir.resolve())
    assert "evil" in out2.name
