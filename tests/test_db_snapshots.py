"""Unit tests for snapshot metadata helpers in src/db/snapshots.py."""

from src.db.snapshots import (
    _build_stable_snapshot_job_id,
    _extract_date_range_from_payload,
)


def test_extract_date_range_normalizes_formats():
    """YYYYMMDD and YYYY-MM-DD are both returned in dashed form."""
    # only start date present
    m1 = {"snapshot_path": "/foo/20230101_snapshot.csv"}
    assert _extract_date_range_from_payload(m1) == ("2023-01-01", "")

    # start and end in YYYY-MM-DD form already
    m2 = {"snapshot_path": "/foo/2023-01-01_to_2023-01-02.csv"}
    assert _extract_date_range_from_payload(m2) == ("2023-01-01", "2023-01-02")

    # mixed styles should both normalize
    m3 = {"snapshot_path": "/foo/20230101-2023-01-02.csv"}
    assert _extract_date_range_from_payload(m3) == ("2023-01-01", "2023-01-02")


def test_extract_date_range_handles_edge_cases():
    """Returns empty range when no dates can be found in metadata."""
    assert _extract_date_range_from_payload({}) == ("", "")
    assert _extract_date_range_from_payload({"other": "x"}) == ("", "")
    assert _extract_date_range_from_payload({"snapshot_path": "/foo/snapshot.csv"}) == (
        "",
        "",
    )


def test_build_stable_snapshot_job_id_ignores_format_variation():
    """Different filename date formats yield identical stable hash."""
    m1 = {"ticker": "PETR4", "snapshot_path": "/x/20230101.csv"}
    m2 = {"ticker": "PETR4", "snapshot_path": "/x/2023-01-01.csv"}

    id1 = _build_stable_snapshot_job_id(m1)
    id2 = _build_stable_snapshot_job_id(m2)
    assert id1 == id2
