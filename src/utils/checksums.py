import hashlib
from pathlib import Path
from typing import Union


def sha256_file(path: Union[str, Path]) -> str:
    """Calculate SHA256 checksum for a file and return the hex digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
