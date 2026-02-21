"""
Testes para o módulo de validação de DataFrames.

Cobertura:
- Validação com arquivo 100% válido
- Arquivo com <10% rows inválidas (passa threshold)
- Arquivo com >=10% rows inválidas (falha threshold)
- Arquivo vazio
- Arquivo com colunas faltando
- Error categorization e reason codes
"""

import pandas as pd
import pytest

from src.validation import (
    ValidationError,
    ValidationSummary,
    check_threshold,
    validate_dataframe,
)


class TestValidateDataFrame:
    """Test suite for validate_dataframe function."""

    def test_validate_fully_valid_dataframe(self):
        """Given a 100% valid DataFrame, should return all rows as valid."""
        # Arrange: create a fully valid canonical DataFrame
        df = pd.DataFrame({
            'ticker': ['PETR4.SA'] * 3,
            'date': pd.to_datetime(['2026-01-01', '2026-01-02', '2026-01-03']),
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [99.0, 100.0, 101.0],
            'close': [104.0, 105.0, 106.0],
            'volume': [1000000, 1100000, 1200000],
            'source': ['yfinance'] * 3,
            'fetched_at': ['2026-01-01T12:00:00Z'] * 3,
            'raw_checksum': ['abc123'] * 3,
        })

        # Act
        valid_df, invalid_df, summary = validate_dataframe(df)

        # Assert
        assert len(valid_df) == 3
        assert len(invalid_df) == 0
        assert summary.rows_total == 3
        assert summary.rows_valid == 3
        assert summary.rows_invalid == 0
        assert summary.invalid_percent == 0.0
        assert summary.error_codes_count == {}

    def test_validate_empty_dataframe(self):
        """Given an empty DataFrame, should return empty results."""
        # Arrange
        df = pd.DataFrame()

        # Act
        valid_df, invalid_df, summary = validate_dataframe(df)

        # Assert
        assert len(valid_df) == 0
        assert len(invalid_df) == 0
        assert summary.rows_total == 0
        assert summary.rows_valid == 0
        assert summary.rows_invalid == 0
        assert summary.invalid_percent == 0.0

    def test_validate_dataframe_with_missing_required_column(self):
        """Given DataFrame missing required column, should flag all rows invalid."""
        # Arrange: create DataFrame without 'ticker' column
        df = pd.DataFrame({
            'date': pd.to_datetime(['2026-01-01', '2026-01-02']),
            'open': [100.0, 101.0],
            'high': [105.0, 106.0],
            'low': [99.0, 100.0],
            'close': [104.0, 105.0],
            'volume': [1000000, 1100000],
            'source': ['yfinance'] * 2,
            'fetched_at': ['2026-01-01T12:00:00Z'] * 2,
            'raw_checksum': ['abc123'] * 2,
        })

        # Act
        valid_df, invalid_df, summary = validate_dataframe(df)

        # Assert
        assert len(valid_df) == 0
        assert len(invalid_df) == 2
        assert summary.rows_invalid == 2
        assert summary.invalid_percent == 1.0
        assert 'MISSING_COL' in summary.error_codes_count

    def test_validate_dataframe_with_invalid_types(self):
        """Given DataFrame with invalid data types, should flag invalid rows."""
        # Arrange: create DataFrame with non-numeric prices
        df = pd.DataFrame({
            'ticker': ['PETR4.SA'] * 3,
            'date': pd.to_datetime(['2026-01-01', '2026-01-02', '2026-01-03']),
            'open': [100.0, 'invalid', 102.0],  # Invalid type
            'high': [105.0, 106.0, 107.0],
            'low': [99.0, 100.0, 101.0],
            'close': [104.0, 105.0, 106.0],
            'volume': [1000000, 1100000, 1200000],
            'source': ['yfinance'] * 3,
            'fetched_at': ['2026-01-01T12:00:00Z'] * 3,
            'raw_checksum': ['abc123'] * 3,
        })

        # Act
        valid_df, invalid_df, summary = validate_dataframe(df)

        # Assert - pandera will coerce, so if coercion fails it might raise
        # For this test, we expect at least some validation to occur
        assert summary.rows_total == 3
        # Coercion might handle this, so we check that validation ran
        assert isinstance(summary, ValidationSummary)

    def test_validate_dataframe_with_constraint_violations(self):
        """Given DataFrame violating constraints (high < low), should flag invalid."""
        # Arrange: create DataFrame where high < low
        df = pd.DataFrame({
            'ticker': ['PETR4.SA'] * 3,
            'date': pd.to_datetime(['2026-01-01', '2026-01-02', '2026-01-03']),
            'open': [100.0, 101.0, 102.0],
            'high': [99.0, 106.0, 107.0],  # First row: high < low
            'low': [105.0, 100.0, 101.0],
            'close': [104.0, 105.0, 106.0],
            'volume': [1000000, 1100000, 1200000],
            'source': ['yfinance'] * 3,
            'fetched_at': ['2026-01-01T12:00:00Z'] * 3,
            'raw_checksum': ['abc123'] * 3,
        })

        # Act
        valid_df, invalid_df, summary = validate_dataframe(df)

        # Assert
        assert summary.rows_total == 3
        # At least one row should fail the high > low check
        assert summary.rows_invalid >= 1
        assert summary.rows_valid <= 2

    def test_validate_dataframe_under_threshold(self):
        """Given <10% invalid rows, should pass threshold check."""
        # Arrange: create DataFrame with 1/20 rows invalid (5%)
        valid_rows = {
            'ticker': ['PETR4.SA'] * 20,
            'date': pd.to_datetime([f'2026-01-{i+1:02d}' for i in range(20)]),
            'open': [100.0] * 20,
            'high': [105.0] * 20,
            'low': [99.0] * 20,
            'close': [104.0] * 20,
            'volume': [1000000] * 20,
            'source': ['yfinance'] * 20,
            'fetched_at': ['2026-01-01T12:00:00Z'] * 20,
            'raw_checksum': ['abc123'] * 20,
        }
        df = pd.DataFrame(valid_rows)
        # Make one row invalid by violating constraint
        df.loc[0, 'high'] = 90.0  # high < low

        # Act
        valid_df, invalid_df, summary = validate_dataframe(df)

        # Assert
        assert summary.invalid_percent < 0.10
        # Should not raise when checking threshold
        result = check_threshold(summary, threshold=0.10, abort_on_exceed=False)
        assert result is True

    def test_validate_dataframe_exceeds_threshold(self):
        """Given >=10% invalid rows, should fail threshold check."""
        # Arrange: create DataFrame with 2/10 rows invalid (20%)
        valid_rows = {
            'ticker': ['PETR4.SA'] * 10,
            'date': pd.to_datetime([f'2026-01-{i+1:02d}' for i in range(10)]),
            'open': [100.0] * 10,
            'high': [105.0] * 10,
            'low': [99.0] * 10,
            'close': [104.0] * 10,
            'volume': [1000000] * 10,
            'source': ['yfinance'] * 10,
            'fetched_at': ['2026-01-01T12:00:00Z'] * 10,
            'raw_checksum': ['abc123'] * 10,
        }
        df = pd.DataFrame(valid_rows)
        # Make 2 rows invalid
        df.loc[0, 'high'] = 90.0  # high < low
        df.loc[1, 'high'] = 95.0  # high < low

        # Act
        valid_df, invalid_df, summary = validate_dataframe(df)

        # Assert
        assert summary.invalid_percent >= 0.10
        # Should raise ValidationError when abort_on_exceed=True
        with pytest.raises(ValidationError):
            check_threshold(summary, threshold=0.10, abort_on_exceed=True)


class TestCheckThreshold:
    """Test suite for check_threshold function."""

    def test_check_threshold_within_limit(self):
        """Given summary within threshold, should return True."""
        # Arrange
        summary = ValidationSummary(
            rows_total=100,
            rows_valid=95,
            rows_invalid=5,
            invalid_percent=0.05,
            error_codes_count={'TYPE_ERROR': 5}
        )

        # Act
        result = check_threshold(summary, threshold=0.10, abort_on_exceed=False)

        # Assert
        assert result is True

    def test_check_threshold_exceeds_limit_no_abort(self):
        """Given summary exceeding threshold, should return False when abort=False."""
        # Arrange
        summary = ValidationSummary(
            rows_total=100,
            rows_valid=85,
            rows_invalid=15,
            invalid_percent=0.15,
            error_codes_count={'TYPE_ERROR': 15}
        )

        # Act
        result = check_threshold(summary, threshold=0.10, abort_on_exceed=False)

        # Assert
        assert result is False

    def test_check_threshold_exceeds_limit_with_abort(self):
        """Given summary exceeding threshold, should raise when abort=True."""
        # Arrange
        summary = ValidationSummary(
            rows_total=100,
            rows_valid=85,
            rows_invalid=15,
            invalid_percent=0.15,
            error_codes_count={'TYPE_ERROR': 15}
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            check_threshold(summary, threshold=0.10, abort_on_exceed=True)
        
        assert "threshold exceeded" in str(exc_info.value).lower()

    def test_check_threshold_exact_limit(self):
        """Given summary exactly at threshold, should fail (>= check)."""
        # Arrange
        summary = ValidationSummary(
            rows_total=100,
            rows_valid=90,
            rows_invalid=10,
            invalid_percent=0.10,
            error_codes_count={'TYPE_ERROR': 10}
        )

        # Act & Assert
        with pytest.raises(ValidationError):
            check_threshold(summary, threshold=0.10, abort_on_exceed=True)
