"""Centralised environment configuration helpers for ingestion.

This module collects logic for parsing and validating the various
environment variables that control the ingest pipeline.  Having a single
location avoids duplication of parsing/validation and makes it easier to
add new knobs or adjust behaviour in the future.

Currently it provides helpers for:

* lock settings used by :func:`src.ingest.pipeline.ingest` (mode and
  timeout).
* snapshot retention (`SNAPSHOTS_KEEP_LATEST`) which is used by both the
  snapshot ingestion layer and the lower-level exporter helpers in
  :mod:`src.etl.snapshot`.
"""

from __future__ import annotations

import os


def get_ingest_lock_settings() -> tuple[float, str, bool]:
    """Read and validate lock settings from the environment.

    Returns ``(timeout_seconds, lock_mode, wait_for_lock)``.

    ``lock_mode`` is always returned in lower case.  ``wait_for_lock`` is a
    convenience boolean that is ``True`` when ``lock_mode`` is ``"wait"``
    (the default) and ``False`` when ``lock_mode`` is ``"exit"``.

    The caller may raise ``ValueError`` if the configured values are not
    parseable or fall outside allowed ranges.  This mirrors the previous
    inline behaviour in :mod:`src.ingest.pipeline` but centralises the
    validation so it can be re-used or tested independently.
    """

    lock_timeout_raw = os.environ.get("INGEST_LOCK_TIMEOUT_SECONDS", "120")
    try:
        lock_timeout = float(lock_timeout_raw)
    except (TypeError, ValueError) as err:
        raise ValueError(
            f"Invalid INGEST_LOCK_TIMEOUT_SECONDS value {lock_timeout_raw!r}: "
            "must be a numeric number of seconds"
        ) from err
    if lock_timeout < 0:
        raise ValueError(
            f"Invalid INGEST_LOCK_TIMEOUT_SECONDS value {lock_timeout_raw!r}: "
            "must be non-negative"
        )

    lock_mode_raw = os.environ.get("INGEST_LOCK_MODE", "wait")
    lock_mode = lock_mode_raw.lower()
    allowed = {"wait", "exit"}
    if lock_mode not in allowed:
        raise ValueError(
            f"Invalid INGEST_LOCK_MODE value {lock_mode_raw!r}: must be one of "
            f"{sorted(allowed)}"
        )

    wait_for_lock = lock_mode != "exit"
    return lock_timeout, lock_mode, wait_for_lock


def get_snapshot_keep_latest() -> int:
    """Return the configured number of snapshots to retain for each ticker.

    The behaviour is identical to the previous ``_snapshot_keep_latest``
    helpers found in :mod:`src.etl.snapshot` and the ad-hoc logic in
    :mod:`src.ingest.snapshot_ingest`.  It defaults to ``1`` and enforces a
    minimum of ``1`` even if a non-positive integer is supplied.  Invalid
    values fall back to the default rather than bubbling an exception; this
    matches the original behaviour.
    """

    raw = os.getenv("SNAPSHOTS_KEEP_LATEST", "1").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1
    return max(1, value)
