from pathlib import Path

from scripts.validate_snapshots import (
    compare_manifests,
    generate_manifest,
    load_manifest,
    write_manifest,
)
from src.utils.checksums import sha256_bytes, sha256_file


def test_generate_and_compare(tmp_path: Path):
    d = tmp_path / "snap"
    d.mkdir()
    f1 = d / "a.txt"
    f1.write_text("hello")
    f2 = d / "b.txt"
    f2.write_text("world")

    manifest = generate_manifest(d)
    assert "".join([]) is not None  # simple sanity
    # write and load using a manifest path
    mpath = tmp_path / "checks.json"
    write_manifest(mpath, manifest)
    loaded = load_manifest(mpath)
    assert isinstance(loaded, dict)

    ok, diffs = compare_manifests(loaded, manifest)
    assert ok is True
    assert diffs == {}


def test_detect_mismatch(tmp_path: Path):
    d = tmp_path / "snap"
    d.mkdir()
    f1 = d / "x.txt"
    f1.write_text("one")

    manifest = generate_manifest(d)
    # mutate file
    f1.write_text("two")
    current = generate_manifest(d)

    ok, diffs = compare_manifests(manifest, current)
    assert ok is False
    # Ensure the changed file is present in current manifest keys
    assert any("x.txt" in p for p in current.keys())


def test_sha256_file_and_bytes(tmp_path):
    data = b"hello-checksum"
    p = tmp_path / "sample.bin"
    p.write_bytes(data)

    file_digest = sha256_file(p)
    bytes_digest = sha256_bytes(data)

    assert file_digest == bytes_digest


def test_serialize_df_warnings_only_once(caplog, monkeypatch):
    """When serialize_df_bytes encounters problems it should warn just once.

    This prevents log spam when the function is called repeatedly in loops.
    The code recently consolidated several per-case guards into a single
    ``_non_deterministic_checksum_warned`` flag; tests need to reset that
    between scenarios so each block remains isolated.
    """
    import pandas as pd

    from src.utils import checksums

    # helper to clear the global warning state between sub-exercises
    def reset_guard():
        checksums._non_deterministic_checksum_warned = False
        # legacy flags were removed; retain this helper for clarity

    # craft a DataFrame with mixed-type column labels to trigger a
    # TypeError during sorting (str vs int).  pandas happily accepts mixed
    # labels, but our helper will hit the exception and log a warning.
    df = pd.DataFrame([[1, 2]], columns=["a", 1])
    caplog.set_level("WARNING")

    reset_guard()
    checksums.serialize_df_bytes(df)
    checksums.serialize_df_bytes(df)
    # should warn about unsortable columns exactly once
    assert caplog.text.count("ordenar colunas") == 1

    # force a reindex failure by monkeypatching DataFrame.reindex to raise
    class BadDF(pd.DataFrame):
        def reindex(self, *args, **kwargs):
            raise RuntimeError("boom")

    df2 = BadDF([[1]])
    caplog.clear()
    caplog.set_level("WARNING")
    reset_guard()
    checksums.serialize_df_bytes(df2)
    checksums.serialize_df_bytes(df2)
    assert caplog.text.count("reindexar colunas") == 1

    # sort_index failure case: use monkeypatch to raise an error so the
    # warning path is exercised.  monkeypatch automatically restores the
    # original attribute at test end.
    caplog.clear()
    caplog.set_level("WARNING")
    reset_guard()

    def _raise_sort(self, *args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(pd.DataFrame, "sort_index", _raise_sort)
    checksums.serialize_df_bytes(pd.DataFrame([[1]]))
    checksums.serialize_df_bytes(pd.DataFrame([[1]]))
    assert "ordenar DataFrame por índice" in caplog.text

    # finally, ensure the global guard suppresses warnings across different
    # failure types if it fires early
    caplog.clear()
    caplog.set_level("WARNING")
    reset_guard()
    checksums.serialize_df_bytes(df)  # triggers unsortable-col warnings
    checksums.serialize_df_bytes(df2)  # reindex issue should be silent now
    assert caplog.text.count("checksum pode ser não-determinístico") == 1
