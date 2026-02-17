---
generated: 2026-02-17T00:00:00Z
source: docs/planning-artifacts/epics.md
owner: Phbr
epic: 7
story: 7.4
status: ready-for-dev
---

# Story 7.4: Test suite orchestration and integration smoke tests

Status: ready-for-dev

## Story

As a QA/Dev,
I want a CI job that orchestrates unit, adapter contract and integration smoke tests (mocked),
so that the core ingest→snapshot→checksum flow is validated on each PR.

## Acceptance Criteria

1. CI job runs linters, unit tests, adapter contract tests (using fixtures), quickstart smoke (`--no-network`) and snapshot checksum validation.
2. The orchestration is runnable via a single orchestrator step (e.g., `.github/workflows/ci.yml` step or `scripts/ci_orchestrator.sh`).
3. Failed runs publish artifacts (CSV, checksum, logs) for debugging.
4. Documentation exists in `docs/ci/migrations.md` describing the job sequence and artifact locations.

## Tasks / Subtasks

- [ ] Add CI job step `ci_orchestrator` to `.github/workflows/ci.yml` that runs: lint → unit → contract → smoke → checksum
  - [ ] Implement `scripts/ci_orchestrator.sh` (or Python script) that sequentially executes the steps and uploads artifacts on failure
- [ ] Add adapter contract tests that run with `--use-fixture` to avoid network calls
- [ ] Add quickstart smoke test mode `--no-network` that uses fixtures and generates snapshot CSV(s)
- [ ] Add checksum validation step computing SHA256 and failing on mismatch
- [ ] Publish failed artifacts in CI job artifacts for debugging
- [ ] Add `tests/ci/` smoke/integration wrappers and example fixtures
- [ ] Update `docs/ci/migrations.md` (or create) with runbook and artifacts retention guidance

## Dev Notes

- Follow existing project conventions: `scripts/` for CI helpers, `tests/` for tests and fixtures in `tests/fixtures/`.
- Use `pytest` CLI with markers: `pytest -m contract` and `pytest -m smoke` for contract and smoke tests.
- Use environment flags to control network access: `--no-network` or env var `CI_NO_NETWORK=true` to enforce fixture usage.
- Orchestrator should run `poetry install --no-dev` where appropriate, and `poetry install` for full test runs in CI matrix.
- Ensure artifacts are stored with predictable names: `artifacts/<job_id>/snapshot.csv`, `artifacts/<job_id>/snapshot.csv.checksum`, `artifacts/<job_id>/logs.tar.gz`.

### Testing Requirements

- Unit tests: `pytest -q --maxfail=1` (fast, deterministic). Add marker `unit`.
- Contract tests: adapter contract tests must run with fixtures and validate expected columns and minimal schema.
- Smoke tests: run quickstart in `--no-network` mode using fixtures to generate snapshots and compute checksums.
- CI must fail if checksum validation fails.

### Project Structure Notes

- Place orchestrator under `scripts/ci_orchestrator.sh` or `scripts/ci_orchestrator.py`.
- Add CI workflow step to `.github/workflows/ci.yml` referencing the orchestrator script.
- Fixtures: `tests/fixtures/sample_ticker.csv` (exists) and additional fixtures under `tests/fixtures/ci/`.

### References

- Source: docs/planning-artifacts/epics.md#Epic-7
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Created story file with acceptance criteria, tasks, dev notes and testing requirements.
- Marked story status as `ready-for-dev` in sprint-status.yaml.

### File List

- docs/implementation-artifacts/7-4-test-suite-orchestration-and-integration-smoke-tests.md
