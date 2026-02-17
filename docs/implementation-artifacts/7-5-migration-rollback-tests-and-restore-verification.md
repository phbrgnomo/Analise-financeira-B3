---
title: "Story 7.5: Migration rollback tests and restore verification"
status: ready-for-dev
epic: 7
story: 7.5
story_key: 7-5-migration-rollback-tests-and-restore-verification
generated_by: create-story workflow
---

# Story 7.5: migration-rollback-tests-and-restore-verification

Status: ready-for-dev

## Story

As an Operator,
I want automated tests that verify migration rollback and restore paths,
so that we can validate recovery procedures and ensure safe schema changes.

## Acceptance Criteria

1. Given a migration set, when the rollback test runs in CI or locally, then it applies migrations, inserts sample data (fixtures), rolls back to a previous version, and verifies that expected constraints and row counts are consistent with the target version.
2. Rollback tests are automated in CI: apply migrations, insert fixture data, run rollback, and then run assertions that verify schema and row counts for restored version; test must be runnable locally with `pytest tests/migrations/test_rollback.py`.
3. The test emits a short JSON summary of the verification results (`passed`, `failed_checks`, `time_ms`) for CI consumption.
4. Tests exercise backup+restore flow where applicable: create backup, apply migration, simulate failure, restore from backup and verify DB integrity (schema + sample rows).

## Tasks / Subtasks

- [ ] Implement test harness `tests/migrations/test_rollback.py` (AC: pytest runnable locally)
  - [ ] Add fixtures for sample DB states under `tests/fixtures/migrations/` (schema versions + sample rows)
  - [ ] Create helper utilities in `migrations/test_utils.py` to programmatically apply migrations, create backups, and run restore verification
  - [ ] Ensure test emits JSON summary to `artifacts/migrations/rollback-summary-<timestamp>.json`
- [ ] Provide lightweight migrations skeleton `migrations/versions` and management commands (status/apply/rollback)
- [ ] Add CI job step `.github/workflows/ci.yml` (or extend existing) to run rollback tests in an isolated temp DB and publish summary artifact
- [ ] Add docs `docs/migrations.md` with runbook steps for local reproduction and restore checklist
- [ ] Add runbook quick commands and remediation steps in `docs/ci/migrations.md`

## Dev Notes

- Test location: `tests/migrations/test_rollback.py`
- Fixtures: `tests/fixtures/migrations/` (provide small SQL dumps or serialized SQLite files)
- Utilities: `migrations/test_utils.py` (apply migrations programmatically, create/verify backups)
- Backup directory: `backups/` (use atomic write: write to temp then rename) + companion `.checksum` file
- Expected commands (local):

```bash
# Apply migrations to temp DB
python -m migrations.cli apply --db temp.db --to head
# Insert fixtures
pytest tests/migrations/test_rollback.py -k full --db temp.db
# Run rollback verification (helper script)
python -m migrations.test_utils run_rollback_test --db temp.db --fixtures tests/fixtures/migrations/
```

## File Structure Notes

- migrations/
  - versions/  # migration scripts
  - __init__.py
  - cli.py     # minimal CLI for apply/status/rollback (used by CI)
- tests/migrations/test_rollback.py
- tests/fixtures/migrations/  # small fixture DBs / SQL dumps
- backups/  # automated backups created by migrations apply
- docs/migrations.md

## Testing Requirements

- Use `pytest` for tests; tests must be deterministic and runnable without network
- Use in-repo fixtures; tests should create isolated temp DBs and clean up after run
- JSON summary format for CI consumption: `{ "job_id": "<id>", "status": "passed|failed", "failed_checks": [], "time_ms": 1234 }`

## References

- Source epic/story: docs/planning-artifacts/epics.md#story-7-5
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used
automated-create-story-runner

### Debug Log References
- create-story workflow run — generated file and sprint-status update

### Completion Notes List
- Story file created from template and epic definitions
- Acceptance criteria and tasks defined; CI and test paths specified

### File List
- docs/implementation-artifacts/7-5-migration-rollback-tests-and-restore-verification.md
