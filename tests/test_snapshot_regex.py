from datetime import datetime

from src.etl import snapshot


def test_snapshot_filename_regex_matches_valid_names():
    names = [
        "PETR4-20260302.csv",
        "ABC123-20200101T120000.csv",
        "TICKER-20211231T235959-extra.csv",
        "PETR4.SA-20230303.csv",
    ]
    pattern = snapshot._SNAPSHOT_FILENAME_RE
    for name in names:
        m = pattern.match(name)
        assert m, f"deveria casar: {name}"
        # ensure ticker group is as expected (uppercase)
        ticker = m.group("ticker")
        assert ticker.upper() == ticker


def test_snapshot_filename_regex_rejects_invalid_names():
    bad = [
        "bad-name.csv",  # no timestamp
        "PETR4-2020-01-01.csv",  # wrong timestamp format
        "petr4-20200101T000000.csv",  # lowercase ticker
        "PETR4_20200101T000000.csv",  # underscore instead of dash
        "PETR4-20200101T000000.txt",  # wrong extension
        "ABC-20200101T000000Z.csv.old",  # extra suffix after .csv
        "PETR4-202603.csv",  # incomplete date-only timestamp
        "PETR4-2026032.csv",  # malformed date-only timestamp (7 digits)
    ]
    pattern = snapshot._SNAPSHOT_FILENAME_RE
    for name in bad:
        assert pattern.match(name) is None, f"não deveria casar: {name}"


def test_parse_snapshot_timestamp_behavior(tmp_path):
    # valid name with Z
    p = tmp_path / "PETR4-20200101T010101Z.csv"
    p.write_text("")
    ts, mtime = snapshot._parse_snapshot_timestamp(p)
    assert isinstance(ts, datetime)
    assert ts == datetime(2020, 1, 1, 1, 1, 1)
    assert isinstance(mtime, float)

    # valid name with date-only timestamp
    p2 = tmp_path / "PETR4-20200101.csv"
    p2.write_text("")
    ts2, mtime2 = snapshot._parse_snapshot_timestamp(p2)
    assert isinstance(ts2, datetime)
    assert ts2 == datetime(2020, 1, 1)
    assert isinstance(mtime2, float)

    # invalid name returns (None, mtime)
    p2 = tmp_path / "foo-bar.csv"
    p2.write_text("")
    ts2, mtime2 = snapshot._parse_snapshot_timestamp(p2)
    assert ts2 is None
    assert isinstance(mtime2, float)
