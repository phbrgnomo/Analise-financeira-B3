def test_importable():
    from src.services.ingest_service import compute_missing_ranges, ensure_prices

    assert callable(ensure_prices)
    assert callable(compute_missing_ranges)
