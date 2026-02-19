"""
Test module for validating CSV snapshots against the canonical schema.

This module tests that example and production CSV files conform to the schema
defined in docs/schema.yaml. It validates:
- Required columns are present
- Column data types are correct
- Business rules are satisfied
- Value constraints are met
"""

import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
import yaml


@pytest.fixture
def schema_definition():
    """Load the canonical schema from docs/schema.yaml."""
    schema_path = Path(__file__).parent.parent / "docs" / "schema.yaml"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    return schema


@pytest.fixture
def example_csv_path():
    """Path to the example CSV file."""
    return Path(__file__).parent.parent / "dados" / "examples" / "ticker_example.csv"


@pytest.fixture
def example_dataframe(example_csv_path):
    """Load the example CSV into a DataFrame with proper types."""
    df = pd.read_csv(
        example_csv_path,
        parse_dates=["date"],
        dtype={
            "ticker": str,
            "source": str,
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "adj_close": float,
            "volume": "Int64",  # Nullable integer
            "raw_checksum": str,
            "Return": float,
        },
    )
    # Convert fetched_at to UTC datetime
    df["fetched_at"] = pd.to_datetime(df["fetched_at"], utc=True)
    return df


class TestSchemaDefinition:
    """Test the schema definition file itself."""

    def test_schema_file_exists(self, schema_definition):
        """Verify schema.yaml exists and is loadable."""
        assert schema_definition is not None
        assert "schema_version" in schema_definition
        assert schema_definition["schema_version"] == 1

    def test_schema_has_required_sections(self, schema_definition):
        """Verify schema has all required sections."""
        required_sections = [
            "schema_version",
            "metadata",
            "columns",
            "versioning",
            "validation",
            "file_format",
            "storage",
        ]
        for section in required_sections:
            assert section in schema_definition, f"Missing section: {section}"

    def test_schema_defines_required_columns(self, schema_definition):
        """Verify schema defines all required columns."""
        required_columns = ["ticker", "date", "source", "fetched_at"]
        column_names = [col["name"] for col in schema_definition["columns"]]

        for required_col in required_columns:
            assert (
                required_col in column_names
            ), f"Required column missing from schema: {required_col}"

    def test_schema_column_definitions_complete(self, schema_definition):
        """Verify each column has complete definition."""
        required_fields = ["name", "type", "nullable", "description"]

        for col in schema_definition["columns"]:
            for field in required_fields:
                assert (
                    field in col
                ), f"Column {col.get('name', 'UNKNOWN')} missing field: {field}"


class TestExampleCSV:
    """Test the example CSV file against the schema."""

    def test_example_csv_exists(self, example_csv_path):
        """Verify the example CSV file exists."""
        assert example_csv_path.exists(), f"Example CSV not found: {example_csv_path}"

    def test_example_csv_loadable(self, example_dataframe):
        """Verify the example CSV is loadable as DataFrame."""
        assert example_dataframe is not None
        assert len(example_dataframe) > 0

    def test_required_columns_present(self, example_dataframe, schema_definition):
        """Verify all required columns are present in example CSV."""
        required_columns = schema_definition["validation"]["required_columns"]

        for col in required_columns:
            assert col in example_dataframe.columns, f"Missing required column: {col}"

    def test_no_unexpected_columns(self, example_dataframe, schema_definition):
        """Verify example CSV doesn't have unexpected columns."""
        schema_columns = {col["name"] for col in schema_definition["columns"]}

        for col in example_dataframe.columns:
            assert (
                col in schema_columns
            ), f"Unexpected column in example CSV: {col}"

    def test_required_columns_not_null(self, example_dataframe, schema_definition):
        """Verify required columns have no null values."""
        required_columns = schema_definition["validation"]["required_columns"]

        for col in required_columns:
            null_count = example_dataframe[col].isna().sum()
            assert null_count == 0, f"Required column {col} has {null_count} null values"

    def test_ticker_format(self, example_dataframe):
        """Verify ticker column meets format constraints."""
        tickers = example_dataframe["ticker"]

        # Must be uppercase alphanumeric
        assert all(
            ticker.isupper() and ticker.replace(".", "").isalnum()
            for ticker in tickers
        ), "All tickers must be uppercase alphanumeric"

        # Max length 10 characters
        assert all(
            len(ticker) <= 10 for ticker in tickers
        ), "All tickers must be <= 10 characters"

    def test_date_format(self, example_dataframe):
        """Verify date column is proper datetime and not in future."""
        dates = example_dataframe["date"]

        # Should be datetime type
        assert pd.api.types.is_datetime64_any_dtype(
            dates
        ), "date column must be datetime type"

        # No future dates
        today = pd.Timestamp.now().normalize()
        assert all(
            dates <= today
        ), "date column must not contain future dates"

    def test_numeric_columns_non_negative(self, example_dataframe):
        """Verify numeric price/volume columns are non-negative when present."""
        numeric_columns = ["open", "high", "low", "close", "adj_close", "volume"]

        for col in numeric_columns:
            if col in example_dataframe.columns:
                non_null_values = example_dataframe[col].dropna()
                if len(non_null_values) > 0:
                    assert (
                        non_null_values >= 0
                    ).all(), f"{col} must be >= 0"

    def test_business_rule_high_low(self, example_dataframe):
        """Verify high >= low for all rows."""
        # Only check rows where both high and low are present
        has_both = example_dataframe["high"].notna() & example_dataframe["low"].notna()
        subset = example_dataframe[has_both]

        if len(subset) > 0:
            assert (
                subset["high"] >= subset["low"]
            ).all(), "high must be >= low"

    def test_business_rule_high_bounds(self, example_dataframe):
        """Verify high >= open and high >= close when all present."""
        # Check high >= open
        has_both = example_dataframe["high"].notna() & example_dataframe["open"].notna()
        subset = example_dataframe[has_both]
        if len(subset) > 0:
            assert (
                subset["high"] >= subset["open"]
            ).all(), "high must be >= open"

        # Check high >= close
        has_both = (
            example_dataframe["high"].notna() & example_dataframe["close"].notna()
        )
        subset = example_dataframe[has_both]
        if len(subset) > 0:
            assert (
                subset["high"] >= subset["close"]
            ).all(), "high must be >= close"

    def test_business_rule_low_bounds(self, example_dataframe):
        """Verify low <= open and low <= close when all present."""
        # Check low <= open
        has_both = example_dataframe["low"].notna() & example_dataframe["open"].notna()
        subset = example_dataframe[has_both]
        if len(subset) > 0:
            assert (
                subset["low"] <= subset["open"]
            ).all(), "low must be <= open"

        # Check low <= close
        has_both = example_dataframe["low"].notna() & example_dataframe["close"].notna()
        subset = example_dataframe[has_both]
        if len(subset) > 0:
            assert (
                subset["low"] <= subset["close"]
            ).all(), "low must be <= close"

    def test_source_format(self, example_dataframe):
        """Verify source column meets format constraints."""
        sources = example_dataframe["source"]

        # Must be lowercase alphanumeric with hyphens
        assert all(
            source.islower() and all(c.isalnum() or c == "-" for c in source)
            for source in sources
        ), "source must be lowercase alphanumeric with hyphens"

        # Max length 50 characters
        assert all(
            len(source) <= 50 for source in sources
        ), "source must be <= 50 characters"

    def test_fetched_at_format(self, example_dataframe):
        """Verify fetched_at is UTC datetime and >= date."""
        fetched_at = example_dataframe["fetched_at"]

        # Should be datetime type with timezone
        assert pd.api.types.is_datetime64_any_dtype(
            fetched_at
        ), "fetched_at must be datetime type"

        # Check fetched_at >= date (can't fetch before trading date)
        # Normalize both to date level for comparison
        dates_only = example_dataframe["date"].dt.normalize()
        fetched_dates = fetched_at.dt.normalize()

        assert (
            fetched_dates >= dates_only
        ).all(), "fetched_at must be >= date"

    def test_raw_checksum_format(self, example_dataframe):
        """Verify raw_checksum is valid SHA256 hex when present."""
        checksums = example_dataframe["raw_checksum"].dropna()

        for checksum in checksums:
            # Must be 64 characters (SHA256 hex length)
            assert (
                len(checksum) == 64
            ), f"raw_checksum must be 64 chars: {checksum}"

            # Must be lowercase hexadecimal
            assert all(
                c in "0123456789abcdef" for c in checksum
            ), f"raw_checksum must be lowercase hex: {checksum}"

    def test_return_calculation_consistency(self, example_dataframe):
        """Verify Return column is consistent with close prices when both present."""
        # Group by ticker to calculate returns
        for ticker in example_dataframe["ticker"].unique():
            ticker_data = example_dataframe[
                example_dataframe["ticker"] == ticker
            ].sort_values("date")

            # Check that Return matches calculated return
            for i in range(1, len(ticker_data)):
                prev_close = ticker_data.iloc[i - 1]["close"]
                curr_close = ticker_data.iloc[i]["close"]
                stated_return = ticker_data.iloc[i]["Return"]

                if (
                    pd.notna(prev_close)
                    and pd.notna(curr_close)
                    and pd.notna(stated_return)
                ):
                    calculated_return = (curr_close - prev_close) / prev_close
                    # Allow small floating point differences
                    assert abs(stated_return - calculated_return) < 0.0001, (
                        f"Return mismatch for {ticker} on {ticker_data.iloc[i]['date']}: "
                        f"stated={stated_return}, calculated={calculated_return}"
                    )


class TestSchemaValidator:
    """Test a generic schema validator function."""

    def test_validate_dataframe_against_schema(
        self, example_dataframe, schema_definition
    ):
        """Test that example DataFrame passes full schema validation."""
        errors = validate_dataframe_against_schema(
            example_dataframe, schema_definition
        )
        assert len(errors) == 0, f"Validation errors: {errors}"


def validate_dataframe_against_schema(df: pd.DataFrame, schema: dict) -> list[str]:
    """
    Validate a DataFrame against the canonical schema.

    Args:
        df: DataFrame to validate
        schema: Schema definition from schema.yaml

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check required columns
    required_columns = schema["validation"]["required_columns"]
    for col in required_columns:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    # Check for unexpected columns
    schema_columns = {col["name"] for col in schema["columns"]}
    for col in df.columns:
        if col not in schema_columns:
            errors.append(f"Unexpected column: {col}")

    # Check required columns are not null
    for col in required_columns:
        if col in df.columns:
            null_count = df[col].isna().sum()
            if null_count > 0:
                errors.append(f"Required column {col} has {null_count} null values")

    # Validate business rules
    business_rules = schema["validation"]["business_rules"]

    # high >= low
    if "high" in df.columns and "low" in df.columns:
        has_both = df["high"].notna() & df["low"].notna()
        if has_both.any() and not (df.loc[has_both, "high"] >= df.loc[has_both, "low"]).all():
            errors.append("Business rule violated: high must be >= low")

    # No future dates
    if "date" in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df["date"]):
            today = pd.Timestamp.now().normalize()
            if (df["date"] > today).any():
                errors.append("Business rule violated: no future dates allowed")

    # fetched_at >= date
    if "date" in df.columns and "fetched_at" in df.columns:
        dates_only = df["date"].dt.normalize()
        fetched_dates = df["fetched_at"].dt.normalize()
        if not (fetched_dates >= dates_only).all():
            errors.append("Business rule violated: fetched_at must be >= date")

    return errors
