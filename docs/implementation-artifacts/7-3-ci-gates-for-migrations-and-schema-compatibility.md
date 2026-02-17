---
title: "7.3 - CI gates for migrations and schema compatibility"
epic: 7
story: 7.3
status: ready-for-dev
created: 2026-02-17T00:00:00Z
owner: CI/Dev
---

# Story 7.3: CI gates for migrations and schema compatibility

Status: ready-for-dev

## Story

As a CI Engineer,
I want CI to validate new migrations in an isolated environment,
so that PRs cannot merge breaking schema changes without verification.

## Acceptance Criteria

1. Given a PR that adds or changes migrations, when CI runs, then it executes a CI job that:
   - runs `migrations status` and reports pending migrations;
   - applies migrations to a temporary/ephemeral DB (isolated environment);
   - runs the test suite (unit + contract + smoke tests) against the migrated DB;
   - tears down and rolls back or destroys the temp DB after tests;
   - fails the PR if migration apply errors, tests fail, or schema drift is detected by `migrations status`.
2. CI job uploads logs and artifacts on failure (migration logs, failed DB dump, CSV/checksum artifacts) for diagnosis.
3. CI defines clear failure modes and a maintainer checklist describing steps to triage blocked PRs (apply error, test failure, schema drift).
4. CI job is runnable locally via a helper script (e.g., `scripts/ci_migrations_check.sh`) to reproduce failures and inspect artifacts.
5. The CI job documents expected commands and outputs in `docs/ci/migrations.md` (runbook) and references `docs/migrations.md` for local migrations tooling.

## Tasks / Subtasks

- [ ] Add CI job definition to `.github/workflows/ci.yml` or extend existing CI matrix with `migrations-check` job
  - [ ] Job: checkout → install deps → `migrations status` → `migrations apply --temp-db` → run tests → teardown
  - [ ] Upload artifacts on failure: logs, db dump, CSV/checksum
- [ ] Implement ephemeral DB support for migrations (e.g., `--temp-db path` or `TMP_DB_URL` env) and ensure `migrations apply` exits non-zero on error
- [ ] Add a helper script `scripts/ci_migrations_check.sh` to orchestrate local reproduction of the CI job
- [ ] Add CI-level configuration for timeouts, retries, and artifact retention
- [ ] Add minimal examples to `docs/ci/migrations.md` and `docs/migrations.md` (commands, common failure modes)

## Dev Notes

- Recommended approach: implement lightweight migrations harness (migrations/ with `__init__.py` + `versions/` skeleton) that can wrap either Alembic or a project-native script interface. Keep CLI surface: `migrations status|apply|rollback`.
- `migrations apply` should accept a `--dry-run`/`--preflight` and a `--temp-db` or `--db-url` override to support ephemeral CI DBs.
- Before applying destructive migrations CI should run `migrations preflight` that reports affected tables and estimated row counts; CI should require `--confirm` only for manual runs.
- Ensure migrations apply step creates a backup when run against persistent DBs (`backups/`) and for CI ephemeral runs the backup step can be no-op.
- Testing: run full pytest suite against the migrated ephemeral DB. Include `tests/migrations/test_rollback.py` to validate rollback path as part of the job.
- Artifacts: on failure upload `migration.log`, `temp_db_dump.sqlite` (or SQL dump), and any generated CSV/checksum artifacts to the CI job.

### Project Structure Notes

- Place migration tooling under `migrations/` with a `versions/` subfolder and an executable CLI entry in `scripts/` or `src/cli`.
- CI job should live in `.github/workflows/ci.yml` and be idempotent; use containers or ephemeral runners to avoid side effects.

### Architecture Compliance / Constraints

- Follow existing project DB abstraction choices (SQLite default in `dados/data.db`) and ensure migrations tool supports SQLite for local dev and CI ephemeral DBs.
- Keep migration metadata in a `schema_version` table as specified by FR34/FR41 in planning artifacts.
- CI must not require network access for core checks; use fixtures and ephemeral DBs for determinism.

### Testing Requirements

- Unit tests + migration integration tests must run in CI job; include contract tests that use fixtures (no external network).
- Add `pytest -q tests/migrations/test_rollback.py` and include it in the CI job sequence.

### References

- Source: docs/planning-artifacts/epics.md#Epic 7 — Testes, CI & Migrações
- See: docs/planning-artifacts/epics.md (Story 7.3 acceptance criteria and suggestions)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Ultimate context engine analysis completed; story created with acceptance criteria, tasks, and dev guardrails.

### File List

- docs/implementation-artifacts/7-3-ci-gates-for-migrations-and-schema-compatibility.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
