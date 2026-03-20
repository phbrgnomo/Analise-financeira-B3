from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

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

    out_path = _assert_safe_snapshot_path(si, df, "../foo/bar.TICK?", snap_dir)
    # filename should have no path separators and illegal chars replaced
    assert ".." not in out_path.name
    assert "/" not in out_path.name
    assert "?" not in out_path.name
    assert "foo_bar_TICK_" in out_path.name

    # even a ticker that looks like a path should be safely mapped
    evil = "..\\evil"  # backslash on windows-like input
    out2 = _assert_safe_snapshot_path(si, df, evil, snap_dir)
    assert "evil" in out2.name


def test_checksum_based_cache_hit_with_different_snapshot_path(tmp_path):
    """Unit-level cache hit test for checksum matches with different snapshot paths."""
    ticker = "PETR4"
    checksum = "abc123"

    old_snapshot_path = tmp_path / "PETR4_20200101.parquet"
    old_snapshot_path.write_text("old")

    new_snapshot_path = tmp_path / "PETR4_20200101_v2.parquet"
    new_snapshot_path.write_text("new")

    cache = {
        str(old_snapshot_path.resolve()): {
            "sha256": checksum,
            "ticker": ticker,
            "processed_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
    }

    result = _check_cache_hit(
        cache_file=cache,
        snapshot_path=new_snapshot_path,
        checksum=checksum,
        ttl=0,
        force=False,
        ticker=ticker,
    )

    assert result is not None
    assert result["cached"] is True
    assert result["reason"] == "checksum_match"
    assert result["snapshot_path"] == str(old_snapshot_path.resolve())


def _assert_safe_snapshot_path(
    si,
    df: pd.DataFrame,
    ticker: str,
    snap_dir: Path,
) -> Path:
    """Assert snapshot path helper for safe snapshot writing.

    This helper invokes ``si._write_snapshot_file(df, ticker, snap_dir)`` and
    validates the result.

    Args:
        si: snapshot interface implementing ``_write_snapshot_file``.
        df: input pandas DataFrame to be snapshotted.
        ticker: ticker symbol string (e.g., 'PETR4').
        snap_dir: target snapshot directory path.

    Returns:
        Path for the created snapshot file.

    Behavior:
        - expects SHA to be ``deadbeef`` (deterministic test data fixture)
        - ensures returned path is inside ``snap_dir``
        - returns the resolved path object for additional assertions
    """
    sha, result = si._write_snapshot_file(df, ticker, snap_dir)
    assert sha == "deadbeef"
    # output path must be inside snapshot directory
    assert result.resolve().is_relative_to(snap_dir.resolve())
    return result
