# Story 1.9: Garantir execução concorrente segura por ticker (lock simples)

Status: ready-for-dev

## Story

As an Operator,
I want the ingest pipeline to prevent concurrent ingests for the same ticker (simple lock),
so that we avoid contention and potential SQLite corruption.

## Acceptance Criteria

1. Given two concurrent `pipeline.ingest --ticker PETR4.SA` requests
   When both start within a small window
   Then the pipeline allows one to run and the other either waits or exits with a clear message (configurable behavior)
   And the behavior is logged to `ingest_logs`.
2. Default locking strategy: filesystem-based lock
   - Default behavior: `wait` with timeout `120` seconds (configurable via `INGEST_LOCK_TIMEOUT_SECONDS`)
   - Alternative behavior: `exit` immediately with clear message (configurable)

## Tasks / Subtasks

- [ ] Implement lock manager utility `src/locks.py` (file-lock wrapper) using `fcntl`/`portalocker` with a simple API:
  - [ ] `acquire_lock(ticker: str, timeout_seconds: int, wait: bool) -> contextmanager`
  - [ ] `release_lock()` automatic via context manager
  - [ ] configurable lock directory via env `LOCK_DIR` (default: `locks/`)
- [ ] Integrate lock manager into `pipeline.ingest` orchestration (check at start, acquire lock, run ingest, finally release)
- [ ] Add logging to `ingest_logs` with fields: `ticker`, `job_id`, `started_at`, `finished_at`, `status`, `lock_action`, `lock_waited_seconds`
- [ ] Add unit/integration tests that spawn two concurrent ingest processes and assert one waits or exits as configured
- [ ] Update CLI docs and playbook with `INGEST_LOCK_TIMEOUT_SECONDS` and example behavior
- [ ] Documentar o que foi implantado nessa etapa em `docs/sprint-reports` conforme definido no FR28 (`docs/planning-artifacts/prd.md`)

## Dev Notes

- Preferred implementation: use cross-platform file lock library `portalocker` (pip). If not available, fallback to POSIX `fcntl.flock` on Unix.
- Important: Keep lock granularity to `per-ticker` only. Do not lock global resources or entire DB file during long-running network calls.
- Lock file path suggestion: `${LOCK_DIR}/{ticker}.lock` (create `locks/` at repo root or configurable path)
- Ensure lock acquisition is short-lived: acquire immediately before DB write/upsert and release right after commit when possible; for safety acquire earlier but keep minimal duration.
- Document behavior when lock timeout occurs: emit structured log and return non-zero exit code when in `exit` mode.

### Implementation suggestions

- Python libs: `portalocker` (recommended), `filelock` (alternative), `fcntl` (POSIX fallback)
- Example approach (POSIX):

```python
import fcntl
with open(lock_path, 'w') as fh:
    fcntl.flock(fh, fcntl.LOCK_EX)
    try:
        # perform critical DB operations
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
```

- Cross-platform example using `portalocker` is preferred for clarity and testability.

## Project Structure Notes

- Suggested new files/locations:
  - `src/locks.py` — lock utilities and context managers
  - `src/pipeline.py` — ensure ingest orchestration uses lock utilities
  - `locks/` — default directory for lock files (gitignored)
  - `tests/test_ingest_lock.py` — concurrency tests (multiprocessing)

## Testing Requirements

- Add integration test that launches two processes calling `poetry run main --ticker PETR4.SA --force-refresh` concurrently and validates:
  - one process completes successfully
  - the other either waits (and later completes) or exits with clear message depending on config
- Add unit tests for `acquire_lock` semantics (timeout, release)

### References

- Source: docs/planning-artifacts/epics.md#Story-1.9
- Related: `docs/planning-artifacts/epics.md` (Epic 1 requirements around concurrency and SQLite limits)

## Dev Agent Record

### Agent Model Used

GPT-5-mini (simulated assistant note: generated story content and checklist)

### Completion Notes List

- Story file created from template and epics source
- Suggested tasks and dev notes added

### File List

- docs/planning-artifacts/epics.md (source)

```

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/122
