import pandas as pd

from src.ingest.pipeline import rows_to_ingest


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
    # rows_to_ingest normalises timezone info but does *not* treat
    # local-time offsets as equivalent to UTC; since the new frame's
    # timestamps are actually 5h later in absolute UTC, all rows look
    # different and should be returned.
    subset = rows_to_ingest(new, existing)
    assert len(subset) == 3
    # indices should be naive after normalization
    assert subset.index.tz is None


def test_rows_to_ingest_detect_change_with_different_tz():
    # same index date but values change; timezone differences shouldn't hide change
    existing = make_df(["2021-01-01"], [1], tz="UTC")
    new = make_df(["2021-01-01"], [9], tz="US/Eastern")
    subset = rows_to_ingest(new, existing)
    assert len(subset) == 1
    assert subset.iloc[0]["val"] == 9


def test_rows_to_ingest_new_and_changed():
    existing = make_df(["2021-01-01"], [1], tz="UTC")
    new = make_df(["2021-01-01", "2021-01-02"], [1, 5], tz="UTC")
    diff = rows_to_ingest(new, existing)
    assert len(diff) == 1
    assert diff.index[0].date() == pd.Timestamp("2021-01-02").date()


def test_rows_to_ingest_ignores_meta_columns():
    existing = make_df(["2021-01-01"], [1], tz=None)
    existing["raw_checksum"] = "a"
    new = make_df(["2021-01-01"], [1], tz=None)
    new["raw_checksum"] = "b"
    diff = rows_to_ingest(new, existing)
    # values identical apart from ignored column, so nothing to ingest
    assert diff.empty


def test_rows_to_ingest_mixed_naive_and_aware():
    # one frame naive, the other timezone-aware; normalization should
    # still compare correctly and drop tz info.
    existing = make_df(["2021-01-01"], [1], tz=None)
    new = make_df(["2021-01-01", "2021-01-02"], [1, 2], tz="UTC")
    subset = rows_to_ingest(new, existing)
    # only the additional date is new; the first row matches after
    # normalization of naive/aware indices.
    assert len(subset) == 1
    assert subset.index[0].date() == pd.Timestamp("2021-01-02").date()
    assert subset.index.tz is None

    # reverse: existing aware, new naive
    existing2 = make_df(["2021-01-01"], [1], tz="UTC")
    new2 = make_df(["2021-01-01", "2021-01-02"], [1, 2], tz=None)
    subset2 = rows_to_ingest(new2, existing2)
    # again only the extra date should be returned
    assert len(subset2) == 1
    assert subset2.index.tz is None


def test_rows_to_ingest_empty_existing():
    # existing is None -> all rows returned
    new = make_df(["2021-01-01", "2021-01-02"], [5, 6], tz="UTC")
    subset = rows_to_ingest(new, None)
    assert len(subset) == 2
    assert subset.index.tz is None

    # empty DataFrame should behave same as None
    empty = pd.DataFrame()
    subset2 = rows_to_ingest(new, empty)
    assert len(subset2) == 2
    assert subset2.index.tz is None
