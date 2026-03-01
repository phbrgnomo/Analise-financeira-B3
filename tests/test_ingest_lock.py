import json
import os
import subprocess
import sys
import time

import pytest

from src import locks


def test_acquire_lock_basic(tmp_path):
    """Simple sanity checks on the lock context manager."""
    os.environ["LOCK_DIR"] = str(tmp_path)
    # grab a lock and hold it manually
    ctx = locks.acquire_lock("T", timeout_seconds=1, wait=True)
    lock_meta = ctx.__enter__()
    assert lock_meta["lock_action"] == "acquired"

    # second non-blocking attempt must fail immediately
    with pytest.raises(locks.LockTimeout):
        with locks.acquire_lock("T", timeout_seconds=0, wait=False):
            pass

    ctx.__exit__(None, None, None)


def test_acquire_lock_timeout(tmp_path):
    """A blocking attempt should honour the timeout parameter."""
    os.environ["LOCK_DIR"] = str(tmp_path)
    # hold the lock
    ctx = locks.acquire_lock("X", timeout_seconds=1, wait=True)
    ctx.__enter__()

    start = time.monotonic()
    with pytest.raises(locks.LockTimeout):
        with locks.acquire_lock("X", timeout_seconds=0.1, wait=True):
            pass
    waited = time.monotonic() - start
    assert waited >= 0.1

    ctx.__exit__(None, None, None)


def run_ingest_process(tmp_path, env_vars):
    """Launch a separate Python process that executes the ingest helper.

    We avoid invoking the Typer CLI directly because the current Typer +
    Python 3.14 combination exhibits parsing bugs (``--source`` is treated
    as a flag).  Instead we run a short ``-c`` snippet which imports
    :func:`ingest_command` and exits with its return code.  This keeps the
    test focused on locking rather than CLI quirks.
    """
    # build a small program that calls ingest_command with dummy provider and
    # ticker "TICK"; environment variables will control locking behavior.
    py = (
        "import sys;"
        "from src.ingest.pipeline import ingest_command;"
        "sys.exit(ingest_command('TICK','dummy', dry_run=True))"
    )
    cmd = [sys.executable, "-c", py]
    env = os.environ.copy()
    env.update(env_vars)
    return subprocess.Popen(
        cmd,
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_concurrent_waiting(tmp_path):
    """When the default "wait" mode is active, the second ingest should
    block until the first one releases the lock and eventually succeed.
    """
    env = {
        "LOCK_DIR": str(tmp_path / "locks"),
        "INGEST_LOCK_TIMEOUT_SECONDS": "2",
        "DUMMY_SLEEP": "1",
    }
    p1 = run_ingest_process(tmp_path, env)
    time.sleep(0.1)  # give p1 a chance to acquire the lock

    env2 = env.copy()
    env2.pop("DUMMY_SLEEP", None)
    p2 = run_ingest_process(tmp_path, env2)

    out1, err1 = p1.communicate(timeout=10)
    out2, err2 = p2.communicate(timeout=10)

    assert p1.returncode == 0
    assert p2.returncode == 0

    # the metadata log should contain lock information for both runs
    log_path = tmp_path / "metadata" / "ingest_logs.jsonl"
    assert log_path.exists(), "expected metadata log to be created"
    lines = [json.loads(line) for line in open(log_path, "r")]  # noqa: SIM102
    assert all("started_at" in entry and "finished_at" in entry for entry in lines), "timestamps missing"
    assert any(entry.get("lock_action") == "acquired" for entry in lines)
    # at least one of the entries should show a non-zero wait time
    assert any(entry.get("lock_waited_seconds", 0) > 0 for entry in lines)


def test_lock_released_on_exception(tmp_path):
    """Context manager should release lock even if an exception is raised.

    Acquire a lock, raise inside the context, then ensure we can acquire it
    again immediately afterwards.  This guards against resource leakage.
    """
    os.environ["LOCK_DIR"] = str(tmp_path)
    # first acquisition that raises
    with pytest.raises(RuntimeError):
        with locks.acquire_lock("Z", timeout_seconds=1, wait=True):
            raise RuntimeError("boom")
    # after the exception, a new acquisition should succeed without timeout
    with locks.acquire_lock("Z", timeout_seconds=0.1, wait=True):
        pass



def test_portalocker_missing_fallback(tmp_path, monkeypatch):
    """If the optional ``portalocker`` dependency is absent, the POSIX
    fallback path should still behave correctly."""
    os.environ["LOCK_DIR"] = str(tmp_path)
    # simulate environment without portalocker
    monkeypatch.setattr(locks, "portalocker", None)
    with locks.acquire_lock("Z", timeout_seconds=0.5, wait=True) as meta:
        assert meta["lock_action"] == "acquired"


def test_concurrent_exit(tmp_path):
    """When mode is set to exit the second process should fail immediately."""
    env = {
        "LOCK_DIR": str(tmp_path / "locks"),
        "INGEST_LOCK_MODE": "exit",
        "DUMMY_SLEEP": "2",
    }
    p1 = run_ingest_process(tmp_path, env)
    time.sleep(0.1)

    env2 = env.copy()
    env2.pop("DUMMY_SLEEP", None)
    p2 = run_ingest_process(tmp_path, env2)

    out1, err1 = p1.communicate(timeout=10)
    out2, err2 = p2.communicate(timeout=10)

    assert p1.returncode == 0
    assert p2.returncode != 0
    assert "lock" in err2.lower()

    # metadata log should record the failed attempt with exit action and no wait
    log_path = tmp_path / "metadata" / "ingest_logs.jsonl"
    assert log_path.exists()
    entries = [json.loads(line) for line in open(log_path, "r")]  # noqa: SIM102
    exit_entries = [e for e in entries if e.get("lock_action") == "exit"]
    assert exit_entries, "expected at least one entry with lock_action 'exit'"
    assert all(e.get("lock_waited_seconds", 0) == 0 for e in exit_entries)
    # failing run should still log metadata with timestamps
    lines = [json.loads(line) for line in open(log_path, "r")]  # noqa: SIM102
    assert all("started_at" in e and "finished_at" in e for e in lines)
