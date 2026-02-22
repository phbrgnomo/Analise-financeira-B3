import pandas as pd
import pytest

from src.validation import _coerce_dataframe_columns


def test_coerce_date_mixed_and_invalid():
    df = pd.DataFrame(
        {
            # use ISO format for predictability under different pandas locales
            "date": ["2020-01-01", "2020-12-31", "not a date"],
            "open": [1.0, 2.0, 3.0],
        }
    )

    # Call
    _coerce_dataframe_columns(df)

    # Date column should be timezone-aware UTC where valid, and NaT where invalid
    from pandas import DatetimeTZDtype

    assert isinstance(df["date"].dtype, DatetimeTZDtype)
    assert not pd.isna(df.loc[0, "date"])
    assert not pd.isna(df.loc[1, "date"])
    assert pd.isna(df.loc[2, "date"])


def test_coerce_numeric_price_mixed_and_unconvertible():
    """Verifica coerção numérica para colunas de preço mistas.

    A função `_coerce_dataframe_columns` deve:
    - converter strings numéricas para floats,
    - transformar valores não convertíveis ou `None` em NaN,
    - preservar valores numéricos já corretos.

    Exemplo: `open` = ["1.23", "bad", None, 4] -> [1.23, NaN, NaN, 4.0].
    """

    df = pd.DataFrame(
        {
            "open": ["1.23", "bad", None, 4],
            "high": ["5.6", "7.8", "9", "x"],
        }
    )

    _coerce_dataframe_columns(df)

    # After coercion, numeric columns should be floats where convertible
    assert df["open"].dtype.kind == "f" or pd.api.types.is_float_dtype(df["open"].dtype)
    assert pd.isna(df.loc[1, "open"])  # 'bad' -> NaN
    assert pd.isna(df.loc[2, "open"])  # None -> NaN
    assert float(df.loc[0, "open"]) == pytest.approx(1.23)
    assert float(df.loc[3, "open"]) == pytest.approx(4.0)

    # high: last value 'x' should be coerced to NaN
    assert pd.isna(df.loc[3, "high"])


def test_coerce_volume_to_nullable_int():
    df = pd.DataFrame(
        {
            "volume": [100, "200", None, "bad"],
        }
    )

    _coerce_dataframe_columns(df)

    # dtype should be pandas nullable integer "Int64"
    assert str(df["volume"].dtype) == "Int64"

    # Values: 100, 200, <NA>, <NA>
    assert int(df.loc[0, "volume"]) == 100
    assert int(df.loc[1, "volume"]) == 200
    assert pd.isna(df.loc[2, "volume"])  # None -> <NA>
    assert pd.isna(df.loc[3, "volume"])  # 'bad' -> <NA>


def test_in_place_modification():
    df = pd.DataFrame({"open": ["1"], "date": ["2021-01-01"]})
    obj_id = id(df)
    _coerce_dataframe_columns(df)
    assert id(df) == obj_id
