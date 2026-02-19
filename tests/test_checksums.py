from src.utils.checksums import sha256_bytes, sha256_file


def test_sha256_file_and_bytes(tmp_path):
    data = b"hello-checksum"
    p = tmp_path / "sample.bin"
    p.write_bytes(data)

    file_digest = sha256_file(p)
    bytes_digest = sha256_bytes(data)

    assert file_digest == bytes_digest
