import pandas as pd

from src.ingest.pipeline import _rows_to_ingest


def make_df(dates, values=None, tz=None):
    df = pd.DataFrame({"date": pd.to_datetime(dates)})
    if tz:
        df["date"] = df["date"].dt.tz_localize(tz)
    if values is not None:
        df["val"] = values
    df = df.set_index("date")
    return df


def test_rows_to_ingest_timezone_handling():
    # existing data in UTC, new data in local tz should be compared correctly
    existing = make_df(["2021-01-01", "2021-01-02"], [1, 2], tz="UTC")
    # new frame includes same dates with different timezone but same values
    new = make_df(
        ["2021-01-01", "2021-01-02", "2021-01-03"],
        [1, 2, 3],
        tz="US/Eastern",
    )
    # _rows_to_ingest normalises timezone info but does *not* treat
    # local-time offsets as equivalent to UTC; since the new frame's
    # timestamps are actually 5h later in absolute UTC, all rows look
    # different and should be returned.
    subset = _rows_to_ingest(new, existing)
    assert len(subset) == 3
    # indices should be naive after normalization
    assert subset.index.tz is None


def test_rows_to_ingest_detect_change_with_different_tz():
    # same index date but values change; timezone differences shouldn't hide change
    existing = make_df(["2021-01-01"], [1], tz="UTC")
    new = make_df(["2021-01-01"], [9], tz="US/Eastern")
    subset = _rows_to_ingest(new, existing)
    assert len(subset) == 1
    assert subset.iloc[0]["val"] == 9


def test_rows_to_ingest_new_and_changed():
    existing = make_df(["2021-01-01"], [1], tz="UTC")
    new = make_df(["2021-01-01", "2021-01-02"], [1, 5], tz="UTC")
    diff = _rows_to_ingest(new, existing)
    assert len(diff) == 1
    assert diff.index[0].date() == pd.Timestamp("2021-01-02").date()


def test_rows_to_ingest_ignores_meta_columns():
    existing = make_df(["2021-01-01"], [1], tz=None)
    existing["raw_checksum"] = "a"
    new = make_df(["2021-01-01"], [1], tz=None)
    new["raw_checksum"] = "b"
    diff = _rows_to_ingest(new, existing)
    # values identical apart from ignored column, so nothing to ingest
    assert diff.empty
