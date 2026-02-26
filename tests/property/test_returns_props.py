import numpy as np
import pandas as pd
import pytest

# Skip this module when Hypothesis is not installed (e.g., minimal CI runners
# or local dev environments without dev deps). CI will install Hypothesis
# when configured via `pyproject.toml`.
pytest.importorskip("hypothesis")
from hypothesis import given
from hypothesis import strategies as st


@given(
    st.lists(
        st.floats(
            min_value=0.01,
            max_value=1000,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=2,
        max_size=20,
    )
)
def test_pct_change_matches_returns_for_generated_series(prices):
    """Generate random positive price series and verify pct_change invariants.

    - returns length == N-1
    - values equal pandas pct_change
    """
    # Build DataFrame similar to canonical input
    dates = pd.date_range("2023-01-01", periods=len(prices), freq="D")
    df = pd.DataFrame({"date": dates, "close": prices})
    # Compute expected pct_change
    expected = pd.Series(prices).pct_change().dropna().reset_index(drop=True)

    # Compute using pandas to mirror compute_returns internal logic
    computed = (
        df.set_index("date")["close"]
        .pct_change()
        .dropna()
        .reset_index(drop=True)
    )

    # Length invariant
    assert len(computed) == len(prices) - 1
    # Value equality to numeric tolerance
    np.testing.assert_allclose(
        computed.values.astype(float), expected.values.astype(float), rtol=0, atol=1e-12
    )
