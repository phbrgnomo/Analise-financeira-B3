import pytest

from src.ingest.snapshot_ingest import _evaluate_cache_hit


def test_generated_at_value_error_logs(caplog):
    """malformed timestamp string should log a warning and be a cache miss."""
    caplog.set_level("WARNING")
    last_meta = {"sha256": "foo", "generated_at": "not-a-timestamp"}
    result = _evaluate_cache_hit(
        last_meta,
        checksum="foo",
        ttl=100,
        force=False,
        ticker="TICK",
    )
    assert result is None
    assert "invalid 'generated_at'" in caplog.text
    assert "not-a-timestamp" in caplog.text
    # ensure we logged the exception message too
    assert "Invalid isoformat string" in caplog.text or "Z" in caplog.text


def test_generated_at_wrong_type_propagates():
    """if generated_at is wrong type (e.g. int) we should not swallow the
    resulting AttributeError; this guards against overly broad exception
    handling.
    """
    last_meta = {"sha256": "foo", "generated_at": 123}
    with pytest.raises(AttributeError):
        _evaluate_cache_hit(
            last_meta,
            checksum="foo",
            ttl=100,
            force=False,
            ticker="TICK",
        )


def test_sanitized_filename_and_path(tmp_path, monkeypatch):
    """Ticker values with separators should be cleaned and file kept inside dir."""
    import pandas as pd

    import src.db as _db
    from src.ingest import snapshot_ingest as si

    # stub out writing and recording to avoid side effects
    monkeypatch.setattr("src.etl.snapshot.write_snapshot", lambda df, path: "deadbeef")
    monkeypatch.setattr(
        _db,
        "record_snapshot_metadata",
        lambda meta, db_path=None: None,
    )

    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir()
    df = pd.DataFrame({"x": [1, 2]})

    # ticker contains traversal and illegal chars
    bad = "../foo/bar.TICK?"
    sha, out_path = si._write_and_record_snapshot(df, bad, snap_dir, db_path=None)
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
    sha2, out2 = si._write_and_record_snapshot(df, evil, snap_dir, db_path=None)
    assert out2.resolve().is_relative_to(snap_dir.resolve())
    assert "evil" in out2.name
