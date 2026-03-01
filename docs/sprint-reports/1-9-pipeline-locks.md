# Sprint Report: Story 1.9 – Per-ticker locking

### Context
Work for Story 1.9 aimed at preventing concurrent ingestion of the same
ticker to avoid SQLite corruption and contention. The mechanism needed to
be simple (filesystem lock), configurable, and observable through existing
metadata logs.

### What was implemented

* New utility module `src/locks.py` providing `acquire_lock` context manager.
  - Uses `portalocker` when available, falling back to POSIX `fcntl`
    with a polling-based timeout loop to ensure cross‑platform use.
  - Exposes timeout and wait/exit semantics configurable via environment
    variables.

* Ingestion orchestration (`src/ingest/pipeline.py`) now acquires a per‑ticker
  lock at the start of `ingest()` and releases it in a `finally` block.
  Behaviour is controlled by `INGEST_LOCK_MODE` and
  `INGEST_LOCK_TIMEOUT_SECONDS`; lock metadata is merged into logging
  context and ingested into `metadata/ingest_logs.jsonl`.
  Dry‑run executions also record lock data for visibility.

* Added CLI documentation and README entries for the new environment
  variables (`INGEST_LOCK_MODE`, `INGEST_LOCK_TIMEOUT_SECONDS`, `LOCK_DIR`).

* Comprehensive tests in `tests/test_ingest_lock.py`:
  - Unit tests for the lock manager (basic acquisition, timeout, non‑blocking
    failure).
  - Integration tests spawning parallel processes to verify default
    "wait" behaviour and immediate "exit" mode, using the `dummy`
    adapter with artificial sleep.
  - Existing pipeline CLI tests were updated with an autouse fixture to
    isolate `LOCK_DIR` and to support the revised execution strategy.

* Fixes and cleanup during implementation:
  - Corrected logging adapter scope to avoid `UnboundLocalError`.
  - Re‑introduced raw CSV persistence accidentally removed during earlier
    refactors.
  - Adjusted `ingest()` to emit metadata during dry runs.
  - Updated type hints to allow floating-point timeouts and removed Python
    3.14 incompatibility with Typer by avoiding CLI in concurrency tests.

### Outcome
The pipeline now safely serialises concurrent requests for the same
ticker and provides clear operational behaviour and logging. All existing
unit and integration tests pass (332 total, zero failures after changes).

### Next steps / follow-up
1. Consider installing `portalocker` in CI environment so the POSIX
   fallback path is exercised less frequently.
2. Add optional startup check that warns if two ingest processes are
   running for the same ticker, to surface contention sooner
   (enhancement to Story 1.9).
3. Update the operational runbook/playbook to include examples of lock
   variables and troubleshooting guidance.

---

Report generated as part of epic-1 development (PR #178).
