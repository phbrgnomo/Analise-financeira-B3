from src import connectivity


def test_provider_connection_uses_adapter_latency(monkeypatch):
    """Ensure wrapper uses latency_ms returned by adapter's check_connection."""

    class FakeAdapter:
        def check_connection(self, timeout=None):
            return {"status": "success", "error": None, "latency_ms": 123.45}

    monkeypatch.setattr(connectivity, "get_adapter", lambda provider: FakeAdapter())

    result = connectivity.test_provider_connection("fake")
    assert result["status"] == "success"
    assert result["latency_ms"] == 123.45


def test_provider_connection_falls_back_to_wrapper_timing(monkeypatch):
    """If the adapter doesn't provide latency, use wrapper-level timing."""

    class FakeAdapter:
        def check_connection(self, timeout=None):
            return {"status": "success", "error": None}

    # Simulate a known duration between calls to time.monotonic.
    calls = [1.0, 1.1]

    def fake_monotonic():
        return calls.pop(0)

    monkeypatch.setattr(connectivity, "get_adapter", lambda provider: FakeAdapter())
    monkeypatch.setattr(connectivity.time, "monotonic", fake_monotonic)

    result = connectivity.test_provider_connection("fake")
    assert result["status"] == "success"
    assert result["latency_ms"] == 100.0
