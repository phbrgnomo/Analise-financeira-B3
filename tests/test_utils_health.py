from datetime import datetime, timezone
from pathlib import Path

from src.utils.health import (
    DEFAULT_INGEST_LOG_NAME,
    compute_health_metrics,
    resolve_ingest_log_path,
)


def test_resolve_ingest_log_path_appends_default_filename_when_default_metadata_is_dir(
    monkeypatch, tmp_path: Path
):
    """Ensure the resolver always returns a full file path.

    When the default metadata path is a directory (or otherwise lacks a suffix),
    we must still append the canonical ingest log filename.
    """

    monkeypatch.delenv("INGEST_LOG_PATH", raising=False)
    monkeypatch.setattr("src.utils.health.DEFAULT_METADATA", tmp_path / "metadata")

    resolved = resolve_ingest_log_path(None)

    assert resolved == str(tmp_path / "metadata" / DEFAULT_INGEST_LOG_NAME)


def test_compute_health_metrics_ignores_future_records(monkeypatch):
    """Future-dated log entries should not count toward last-24h metrics."""

    fixed_now = datetime(2026, 3, 19, 0, 0, tzinfo=timezone.utc)

    # Force the health module to consider a fixed "now" for deterministic tests.
    import src.utils.health as health

    class FakeDatetime:
        @classmethod
        def now(cls, tz=None):
            return fixed_now

        @classmethod
        def fromisoformat(cls, dt_str: str):
            return datetime.fromisoformat(dt_str)

    monkeypatch.setattr(health, "datetime", FakeDatetime)

    logs = [
        # Within last 24h (should count)
        {"status": "success", "finished_at": "2026-03-18T12:00:00Z"},
        # Within last 24h but failure (should count as error)
        {"status": "failure", "finished_at": "2026-03-18T13:00:00Z"},
        # Future timestamp (should NOT be counted)
        {"status": "failure", "finished_at": "2026-03-20T00:00:00Z"},
    ]

    result = compute_health_metrics(logs, threshold_seconds=3600)

    assert result["metrics"]["jobs_last_24h"] == 2
    assert result["metrics"]["errors_last_24h"] == 1
