from datetime import datetime, timedelta, timezone

import pytest

from src.etl.mapper import parse_date_strict


def test_parse_date_strict_valid():
    dt = parse_date_strict("2023-06-15")
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2023 and dt.month == 6 and dt.day == 15


def test_parse_date_strict_invalid_format():
    with pytest.raises(ValueError):
        parse_date_strict("not-a-date")


def test_parse_date_strict_future_date():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError):
        parse_date_strict(future)


def test_parse_date_strict_pre_2000():
    with pytest.raises(ValueError):
        parse_date_strict("1990-01-01")
