import pandas as pd

from src.validation import validate_dataframe


def test_numeric_and_date_normalization():
    """Normalização de strings numéricas e de datas para tipos apropriados.

    Cenário: colunas de data e numéricas são fornecidas como strings e devem
    ser convertidas para tipos datetime e numéricos respectivamente.
    """
    # Arrange: data como strings, numéricos como strings
    df = pd.DataFrame(
        {
            "ticker": ["PETR4.SA"],
            "date": ["2026-01-01"],
            "open": ["100.0"],
            "high": ["105.0"],
            "low": ["99.0"],
            "close": ["104.0"],
            "volume": ["1000000"],
            "source": ["yfinance"],
            "fetched_at": ["2026-01-01T12:00:00Z"],
            "raw_checksum": ["abc123"],
        }
    )

    # Act (ação)
    valid_df, invalid_df, summary = validate_dataframe(df)

    # Assert (verificação): coercão deve permitir que a linha seja válida
    assert summary.rows_invalid == 0
    assert summary.rows_valid == 1
    # a coluna date deve ser convertida para datetime
    assert pd.api.types.is_datetime64_any_dtype(valid_df["date"])
    # colunas numéricas devem ser do tipo numérico
    for c in ("open", "high", "low", "close"):
        assert pd.api.types.is_float_dtype(valid_df[c])
    assert pd.api.types.is_integer_dtype(valid_df["volume"].dtype) or str(
        valid_df["volume"].dtype
    ).startswith("Int64")
