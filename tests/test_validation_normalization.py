from datetime import date, timedelta

import pandas as pd

from src import validation


def test_date_and_fetched_at_normalization():
    df = pd.DataFrame(
        {
            "date": ["2021-03-01", "2021-03-02T05:00:00Z"],
            "fetched_at": ["2021-03-01T12:00:00Z", "2021-03-02T13:30:00+00:00"],
        }
    )

    validation._coerce_dataframe_columns(df)

    # date column should contain python date objects (date-only)
    assert isinstance(df.at[0, "date"], date)
    assert isinstance(df.at[1, "date"], date)

    # fetched_at should be timezone-aware and in UTC
    fa0 = df.at[0, "fetched_at"]
    fa1 = df.at[1, "fetched_at"]
    assert fa0.tzinfo is not None
    assert fa1.tzinfo is not None
    # both normalized to UTC (zero offset)
    assert fa0.tzinfo is not None and fa0.tzinfo.utcoffset(fa0) == timedelta(0)
    assert fa1.tzinfo is not None and fa1.tzinfo.utcoffset(fa1) == timedelta(0)
