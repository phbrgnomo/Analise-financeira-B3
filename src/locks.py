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


def _resolve_lock_dir(env_val: str | None) -> Path:
    """Return a resolved Path for the lock directory.

    Expands ~ and resolves to an absolute path.
    """
    val = env_val if env_val is not None else str(DEFAULT_LOCK_DIR)
    return Path(val).expanduser().resolve()


def _acquire_with_portalocker(
    fh, flags, wait: bool, timeout_seconds: float, start: float, ticker: str
) -> None:
    """Acquire lock using portalocker or raise LockTimeout on failure."""
    try:
        portalocker.lock(
            fh, flags, timeout=timeout_seconds if wait else 0
        )
    except portalocker.exceptions.LockException as exc:
        waited = time.monotonic() - start
        if not wait:
            raise LockTimeout(
                f"lock for {ticker} held by another process (non-blocking)"
            ) from exc
        raise LockTimeout(
            f"failed to acquire lock for {ticker} after {waited:.3f}s"
        ) from exc


def _acquire_with_fcntl(
    fh, wait: bool, timeout_seconds: float, start: float, ticker: str
) -> None:
    """Acquire lock using POSIX fcntl with optional timeout polling."""
    import fcntl

    if not wait:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as exc:
            raise LockTimeout(
                f"lock for {ticker} held by another process (non-blocking)"
            ) from exc

    end = start + timeout_seconds
    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as exc:
            if (
                timeout_seconds is not None
                and time.monotonic() >= end
            ):
                waited = time.monotonic() - start
                raise LockTimeout(
                    f"failed to acquire lock for {ticker} after {waited:.3f}s"
                ) from exc
            time.sleep(0.05)


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
    lock_dir = _resolve_lock_dir(os.environ.get("LOCK_DIR"))
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
            _acquire_with_portalocker(
                fh, flags, wait, timeout_seconds, start, ticker
            )
            locked = True
        else:
            _acquire_with_fcntl(fh, wait, timeout_seconds, start, ticker)
            locked = True
    except Exception:
        # acquisition failed; clean up the file handle and re-raise
        fh.close()
        raise

    try:
        waited = time.monotonic() - start
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
