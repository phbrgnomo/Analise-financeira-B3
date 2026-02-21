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
    assert "files" in loaded

    ok, diffs = compare_manifests(loaded.get("files"), manifest)
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
