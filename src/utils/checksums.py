"""Checksum utilities.

Small helpers to compute SHA256 checksums for files and bytes.
"""

import hashlib
from pathlib import Path
from typing import Union


def sha256_file(path: Union[str, Path]) -> str:
    """Calculate SHA256 checksum for a file and return the hex digest.

    Args:
        path: Path-like or string to the file to hash.

    Returns:
        Hex digest string of the SHA256 hash.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return SHA256 hex digest for the given bytes."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


__all__ = ["sha256_file", "sha256_bytes"]
