

import json
from datetime import datetime, timedelta, timezone

from src.ingest import cache


def test_save_cache_handles_unserializable(tmp_path, caplog):
    path = tmp_path / "cache.json"
    # object with a non-serializable value
    bad = {"a": complex(1, 2)}

    caplog.set_level("WARNING")
    cache.save_cache(path, bad)

    # logger warning should mention failure and path
    assert "failed to write snapshot cache" in caplog.text.lower()
    # temp file should be removed
    tmp = path.with_suffix(path.suffix + ".tmp")
    assert not tmp.exists()

    # original cache file should not have been created
    assert not path.exists()


def test_load_cache_returns_valid_data(tmp_path):
    path = tmp_path / "cache.json"
    expected = {"foo": "bar", "n": 1}

    # write a valid JSON cache file
    path.write_text(json.dumps(expected), encoding="utf-8")

    result = cache.load_cache(path)

    assert result == expected


def test_load_cache_invalid_json_logs_warning_and_returns_empty(tmp_path, caplog):
    path = tmp_path / "cache.json"
    # write an invalid JSON payload
    path.write_text("{invalid json}", encoding="utf-8")

    caplog.set_level("WARNING")
    result = cache.load_cache(path)

    # should fall back to empty dict
    assert result == {}
    # should log a warning mentioning failure and the path
    text = caplog.text.lower()
    assert "failed" in text
    assert "cache" in text
    assert str(path) in caplog.text


def test_entry_is_fresh_for_recent_entry():
    now = datetime.now(timezone.utc)
    entry = {"processed_at": now.isoformat()}

    assert cache.entry_is_fresh(entry, ttl=60) is True


def test_entry_is_not_fresh_when_expired():
    now = datetime.now(timezone.utc)
    entry = {"processed_at": (now - timedelta(seconds=120)).isoformat()}

    assert cache.entry_is_fresh(entry, ttl=60) is False


def test_entry_is_not_fresh_for_malformed_timestamp():
    entry = {"processed_at": "not-a-timestamp"}

    assert cache.entry_is_fresh(entry, ttl=60) is False
