"""
Integration smoke test for canonical mapper with mock provider.

Verifies that canonical output shape can be consumed by DB layer.
"""

import pandas as pd

from src.etl.mapper import to_canonical


class TestCanonicalMapperIntegration:
    """Integration tests for canonical mapper with downstream consumers."""

    def test_canonical_output_shape_for_db_layer(self):
        """
        Verify canonical DataFrame has correct shape/types for DB upsert.

        This is a smoke test that validates the canonical mapper produces
        output compatible with the expected DB schema (even if DB layer
        doesn't exist yet).
        """
        # Arrange: create mock provider response (yfinance-like)
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        mock_provider_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "High": [105.0, 106.0, 107.0, 108.0, 109.0],
                "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "Close": [104.0, 105.0, 106.0, 107.0, 108.0],
                "Adj Close": [103.5, 104.5, 105.5, 106.5, 107.5],
                "Volume": [1000000, 1100000, 1200000, 1300000, 1400000],
            },
            index=dates,
        )

        # Act: convert to canonical
        canonical_df = to_canonical(
            mock_provider_df, provider_name="mock_provider", ticker="TEST.SA"
        )

        # Assert: DB-compatible structure
        assert not canonical_df.empty
        assert len(canonical_df) == 5

        # Verify all required columns for DB upsert are present
        expected_columns = {
            "ticker",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source",
            "fetched_at",
            "raw_checksum",
        }
        assert set(canonical_df.columns) == expected_columns

        # Verify types are compatible with SQLite/DB schema
        assert canonical_df["ticker"].dtype == object  # string
        assert pd.api.types.is_datetime64_any_dtype(canonical_df["date"])
        assert pd.api.types.is_float_dtype(canonical_df["open"])
        assert pd.api.types.is_float_dtype(canonical_df["high"])
        assert pd.api.types.is_float_dtype(canonical_df["low"])
        assert pd.api.types.is_float_dtype(canonical_df["close"])
        assert pd.api.types.is_integer_dtype(canonical_df["volume"])
        assert canonical_df["source"].dtype == object  # string
        # fetched_at should be a datetime dtype per canonical schema
        assert pd.api.types.is_datetime64_any_dtype(
            canonical_df["fetched_at"]
        )

        # Verify metadata for audit/provenance
        assert "raw_checksum" in canonical_df.attrs
        assert "provider" in canonical_df.attrs
        assert "ticker" in canonical_df.attrs
        assert canonical_df.attrs["provider"] == "mock_provider"
        assert canonical_df.attrs["ticker"] == "TEST.SA"

    def test_canonical_output_ready_for_upsert_operation(self):
        """
        Verify canonical DataFrame supports upsert key (ticker, date).

        DB layer is expected to upsert by composite key (ticker, date).
        This test verifies the canonical output includes those columns
        with no duplicates.
        """
        # Arrange
        dates = pd.date_range("2026-01-01", periods=3, freq="D")
        mock_df = pd.DataFrame(
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
        canonical_df = to_canonical(mock_df, provider_name="test", ticker="PETR4.SA")

        # Assert: upsert key columns present
        assert "ticker" in canonical_df.columns
        assert "date" in canonical_df.columns

        # Assert: no duplicate keys (ticker, date) - upsert requirement
        duplicate_keys = canonical_df.duplicated(subset=["ticker", "date"])
        assert not duplicate_keys.any(), "Found duplicate (ticker, date) keys"

        # Assert: all ticker values are consistent
        assert canonical_df["ticker"].nunique() == 1
        assert canonical_df["ticker"].iloc[0] == "PETR4.SA"
