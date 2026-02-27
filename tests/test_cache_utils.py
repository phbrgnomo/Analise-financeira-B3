

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
