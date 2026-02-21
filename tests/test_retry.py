from unittest.mock import patch

import pandas as pd

from src.adapters.retry_config import RetryConfig
from src.adapters.retry_metrics import get_global_metrics
from src.adapters.yfinance_adapter import YFinanceAdapter


def test_retry_config_compute_delay_ms():
    rc = RetryConfig(
        max_attempts=5,
        initial_delay_ms=500,
        max_delay_ms=2000,
        backoff_factor=2.0,
    )
    assert rc.compute_delay_ms(1) == 500
    assert rc.compute_delay_ms(2) == 1000
    assert rc.compute_delay_ms(3) == 2000
    assert rc.compute_delay_ms(10) == 2000



@patch("src.adapters.yfinance_adapter.web.DataReader")
@patch("src.adapters.base.time.sleep")
def test_metrics_are_recorded_on_retries(mock_sleep, mock_datareader):
    metrics = get_global_metrics()
    metrics.reset()

    dates = pd.date_range("2024-01-01", periods=2)
    success_df = pd.DataFrame(
        {
            "Open": [100, 101],
            "High": [105, 106],
            "Low": [99, 100],
            "Close": [102, 103],
            "Adj Close": [102, 103],
            "Volume": [1000, 1100],
        },
        index=dates,
    )

    mock_datareader.side_effect = [ConnectionError("Network timeout"), success_df]

    adapter = YFinanceAdapter(max_retries=3)
    # Executar fetch para acionar os retries; não precisamos do objeto retornado aqui
    adapter.fetch("PETR4")

    m = get_global_metrics().to_dict()
    assert m["retry_count"] >= 1
    assert m["success_after_retry"] >= 1
    assert m["total_attempts"] >= 2
