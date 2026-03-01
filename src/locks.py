"""Simple cross-platform file lock utility for per-ticker ingestion.

A thin wrapper around ``portalocker`` (preferred) with a POSIX ``fcntl``
fallback when ``portalocker`` is not installed.  The API is deliberately
small so that calling code can use a ``with`` block or ``@contextmanager``
idiom.

This module is intentionally self-contained and has no external dependencies
beyond the standard library; ``portalocker`` is optional and only used when
available.  All configuration is driven by environment variables to keep the
pipeline code simple and easy to test.

Classes
-------
LockTimeout
    Exception thrown when a lock cannot be acquired in the requested mode.

Functions
---------
acquire_lock(ticker, timeout_seconds=120, wait=True) -> contextmanager
    Context manager that obtains an exclusive lock on ``{LOCK_DIR}/{ticker}.lock``
    and releases it automatically on exit.

"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

try:
    import portalocker
except ImportError:  # pragma: no cover - tests will install portalocker
    portalocker = None


# default directory where lock files are stored; overridable via LOCK_DIR
# Keep a Path object as default but resolve at runtime from the env var.
DEFAULT_LOCK_DIR = Path("locks")


class LockTimeout(Exception):
    """Raised when a lock request cannot be satisfied under the configured
    timeout/behavior.
    """


@contextmanager
def acquire_lock(
    ticker: str, timeout_seconds: float = 120.0, wait: bool = True
) -> Iterator[Dict[str, Any]]:
    """Acquire a filesystem lock for a given ticker.

    Parameters
    ----------
    ticker : str
        The ticker name; the lock file will be ``{LOCK_DIR}/{ticker}.lock``.
    timeout_seconds : int
        Maximum time to wait for the lock when ``wait`` is True.  When
        ``wait`` is False the lock attempt is non-blocking and this value is
        ignored (an immediate ``LockTimeout`` will be raised if the file is
        already locked).
    wait : bool
        If ``True`` block until the lock is available or ``timeout_seconds``
        elapses.  ``False`` causes the call to fail immediately if the lock is
        held by another process.

    Yields
    ------
    dict
        Informational dictionary with keys ``lock_action`` ("acquired" or
        "timeout") and ``lock_waited_seconds`` (float).

    Raises
    ------
    LockTimeout
        When the lock cannot be acquired in the requested mode.
    """

    # respect explicit env var, allow ~ expansion, and resolve to absolute path
    lock_dir = Path(os.environ.get("LOCK_DIR", str(DEFAULT_LOCK_DIR))).expanduser().resolve()
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{ticker}.lock"

    # open file descriptor now so it remains valid until the context exits or
    # until we give up acquiring the lock.  If acquisition fails we must make
    # sure to close the handle immediately to avoid resource leaks.
    fh = open(lock_path, "a+")
    start = time.monotonic()
    locked = False

    # acquisition logic is isolated in its own try so we can react to failures
    # by closing ``fh`` before bubbling the error up.  After this block the
    # handle remains open until the ``finally`` below, which will release the
    # lock (if held) and close the file.
    try:
        if portalocker is not None:
            flags = portalocker.LockFlags.EXCLUSIVE
            if not wait:
                flags |= portalocker.LockFlags.NON_BLOCKING
            try:
                # portalocker supports a timeout argument when blocking behavior is
                # desired; when ``wait`` is False we pass 0 to force immediate
                # failure instead of waiting.
                portalocker.lock(fh, flags, timeout=timeout_seconds if wait else 0)
                locked = True
            except portalocker.exceptions.LockException as exc:
                waited = time.monotonic() - start
                if not wait:
                    raise LockTimeout(
                        f"lock for {ticker} is held by another process (non-blocking mode)"
                    ) from exc
                raise LockTimeout(
                    f"failed to acquire file lock for {ticker} after {waited:.3f}s"
                ) from exc
        else:
            # fallback to POSIX flock; this will only work on Unix-like
            # platforms.  ``fcntl`` doesn't support a timeout, so we implement
            # a simple polling loop when ``wait`` is True and ``timeout_seconds``
            # is specified.  This keeps the public API consistent regardless of
            # whether ``portalocker`` is installed.
            import fcntl

            if not wait:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except BlockingIOError as exc:
                    raise LockTimeout(
                        f"lock for {ticker} is held by another process (non-blocking mode)"
                    ) from exc
            else:
                end = start + timeout_seconds
                while True:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = True
                        break
                    except BlockingIOError:
                        if timeout_seconds is not None and time.monotonic() >= end:
                            waited = time.monotonic() - start
                            raise LockTimeout(
                                f"failed to acquire file lock for {ticker} after {waited:.3f}s"
                            )
                        # sleep briefly to avoid busy-looping
                        time.sleep(0.05)
    except Exception:
        # acquisition failed; clean up the file handle and re‑raise
        fh.close()
        raise

    # if we reach here the lock has been acquired successfully; ``fh`` will
    # remain open until the ``finally`` block below closes it.
    waited = time.monotonic() - start
    try:
        yield {"lock_action": "acquired", "lock_waited_seconds": waited}
    finally:
        if locked:
            try:
                if portalocker is not None:
                    portalocker.unlock(fh)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:  # pragma: no cover - best effort
                pass
        fh.close()
