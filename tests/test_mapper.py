"""
Tests for the canonical mapper (provider DataFrame -> canonical schema).

Covers:
- Successful mapping from yfinance-like input to canonical schema
- Handling of missing columns (fail with clear error)
- raw_checksum correctness for example payloads
- Validation using pandera schema
"""

import hashlib

import pandas as pd
import pytest

from src.etl.mapper import CanonicalSchema, MappingError, to_canonical


class TestToCanonical:
    """Test suite for to_canonical function."""

    def test_successful_mapping_from_yfinance(self):
        """Given a yfinance-like DataFrame, should return canonical format."""
        # Arrange: create a yfinance-like DataFrame
        dates = pd.date_range("2026-01-01", periods=3, freq="D")
        raw_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [105.0, 106.0, 107.0],
                "Low": [99.0, 100.0, 101.0],
                "Close": [104.0, 105.0, 106.0],
                "Adj Close": [103.5, 104.5, 105.5],
                "Volume": [1000000, 1100000, 1200000],
            },
            index=dates,
        )

        # Act
        result = to_canonical(raw_df, provider_name="yfinance", ticker="PETR4.SA")

        # Assert: canonical columns present
        expected_columns = [
            "ticker",
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "source",
            "fetched_at",
            "raw_checksum",
        ]
        assert list(result.columns) == expected_columns

        # Assert: data correctness
        assert result["ticker"].iloc[0] == "PETR4.SA"
        assert result["source"].iloc[0] == "yfinance"
        assert result["open"].iloc[0] == 100.0
        assert result["adj_close"].iloc[0] == 103.5

        # Assert: fetched_at is UTC ISO8601
        fetched_at = result["fetched_at"].iloc[0]
        assert isinstance(fetched_at, str)
        assert fetched_at.endswith("Z") or "+" in fetched_at

        # Assert: metadata includes raw_checksum
        assert "raw_checksum" in result.attrs
        assert isinstance(result.attrs["raw_checksum"], str)
        assert len(result.attrs["raw_checksum"]) == 64  # SHA256 hex digest

    def test_missing_required_columns_raises_error(self):
        """Given a DataFrame missing required columns, should raise MappingError."""
        # Arrange: DataFrame missing 'Close' column
        dates = pd.date_range("2026-01-01", periods=2, freq="D")
        raw_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [105.0, 106.0],
                "Low": [99.0, 100.0],
                # Missing 'Close', 'Adj Close', 'Volume'
            },
            index=dates,
        )

        # Act & Assert
        with pytest.raises(MappingError) as exc_info:
            to_canonical(raw_df, provider_name="yfinance", ticker="TEST")

        assert "missing required columns" in str(exc_info.value).lower()

    def test_raw_checksum_correctness(self):
        """Given a known DataFrame, raw_checksum should be deterministic."""
        # Arrange
        dates = pd.date_range("2026-01-01", periods=2, freq="D")
        raw_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [105.0, 106.0],
                "Low": [99.0, 100.0],
                "Close": [104.0, 105.0],
                "Adj Close": [103.5, 104.5],
                "Volume": [1000000, 1100000],
            },
            index=dates,
        )

        # Act: call mapper twice
        result1 = to_canonical(raw_df.copy(), provider_name="test", ticker="TEST1")
        result2 = to_canonical(raw_df.copy(), provider_name="test", ticker="TEST1")

        # Assert: checksums should match
        assert result1.attrs["raw_checksum"] == result2.attrs["raw_checksum"]

        # Verify checksum is actually SHA256 of CSV representation
        csv_bytes = raw_df.to_csv(index=True).encode("utf-8")
        expected_checksum = hashlib.sha256(csv_bytes).hexdigest()
        assert result1.attrs["raw_checksum"] == expected_checksum

    def test_canonical_schema_validation(self):
        """Given canonical DataFrame, pandera schema should validate it."""
        # Arrange
        dates = pd.date_range("2026-01-01", periods=2, freq="D")
        raw_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [105.0, 106.0],
                "Low": [99.0, 100.0],
                "Close": [104.0, 105.0],
                "Adj Close": [103.5, 104.5],
                "Volume": [1000000, 1100000],
            },
            index=dates,
        )

        # Act
        canonical_df = to_canonical(raw_df, provider_name="test", ticker="TEST")

        # Assert: schema validation should pass without exception
        validated_df = CanonicalSchema.validate(canonical_df)
        assert validated_df is not None
        assert len(validated_df) == 2

    def test_invalid_types_fail_validation(self):
        """Given DataFrame with wrong types, pandera should raise validation error."""
        # Arrange: create DataFrame with string in numeric column
        dates = pd.date_range("2026-01-01", periods=2, freq="D")
        raw_df = pd.DataFrame(
            {
                "Open": ["invalid", 101.0],  # String in numeric column
                "High": [105.0, 106.0],
                "Low": [99.0, 100.0],
                "Close": [104.0, 105.0],
                "Adj Close": [103.5, 104.5],
                "Volume": [1000000, 1100000],
            },
            index=dates,
        )

        # Act & Assert: should raise MappingError during validation
        with pytest.raises(MappingError) as exc_info:
            to_canonical(raw_df, provider_name="test", ticker="TEST")

        assert "validation" in str(exc_info.value).lower()

    def test_empty_dataframe_raises_error(self):
        """Given empty DataFrame, should raise MappingError."""
        # Arrange
        raw_df = pd.DataFrame()

        # Act & Assert
        with pytest.raises(MappingError) as exc_info:
            to_canonical(raw_df, provider_name="test", ticker="TEST")

        assert "empty" in str(exc_info.value).lower()

    def test_timezone_normalization_to_utc(self):
        """Verify fetched_at is normalized to UTC ISO8601."""
        # Arrange
        dates = pd.date_range("2026-01-01", periods=1, freq="D")
        raw_df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Close": [104.0],
                "Adj Close": [103.5],
                "Volume": [1000000],
            },
            index=dates,
        )

        # Act
        result = to_canonical(raw_df, provider_name="test", ticker="TEST")

        # Assert: fetched_at should be ISO8601 UTC
        fetched_at = result["fetched_at"].iloc[0]
        # Parse and verify it's valid UTC timestamp
        assert "T" in fetched_at  # ISO8601 format
        # Should end with Z or have timezone info
        assert fetched_at.endswith("Z") or "+" in fetched_at or "-" in fetched_at[-6:]

    def test_metadata_preserved_in_attrs(self):
        """Verify metadata (raw_checksum, provider, ticker) is stored in attrs."""
        # Arrange
        dates = pd.date_range("2026-01-01", periods=1, freq="D")
        raw_df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Close": [104.0],
                "Adj Close": [103.5],
                "Volume": [1000000],
            },
            index=dates,
        )

        # Act
        result = to_canonical(raw_df, provider_name="alphavantage", ticker="AAPL")

        # Assert: attrs should contain metadata
        assert "raw_checksum" in result.attrs
        assert "provider" in result.attrs
        assert "ticker" in result.attrs
        assert result.attrs["provider"] == "alphavantage"
        assert result.attrs["ticker"] == "AAPL"
