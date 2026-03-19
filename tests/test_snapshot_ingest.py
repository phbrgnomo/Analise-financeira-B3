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

    out_path = _extracted_from_test_sanitized_filename_and_path_16(
        si, df, "../foo/bar.TICK?", snap_dir
    )
    # filename should have no path separators and illegal chars replaced
    assert ".." not in out_path.name
    assert "/" not in out_path.name
    assert "?" not in out_path.name
    assert "foo_bar_TICK_" in out_path.name

    # even a ticker that looks like a path should be safely mapped
    evil = "..\\evil"  # backslash on windows-like input
    out2 = _extracted_from_test_sanitized_filename_and_path_16(
        si, df, evil, snap_dir
    )
    assert "evil" in out2.name


# TODO Rename this here and in `test_sanitized_filename_and_path`
def _extracted_from_test_sanitized_filename_and_path_16(si, df, arg2, snap_dir):
    sha, result = si._write_snapshot_file(df, arg2, snap_dir)
    assert sha == "deadbeef"
    # output path must be inside snapshot directory
    assert result.resolve().is_relative_to(snap_dir.resolve())
    return result
