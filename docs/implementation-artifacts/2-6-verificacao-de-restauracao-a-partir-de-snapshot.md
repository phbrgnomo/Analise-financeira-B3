---
story_key: 2-6-verificacao-de-restauracao-a-partir-de-snapshot
epic: 2
story_num: 6
status: ready-for-dev
owner: Phbr
created: 2026-02-17T00:00:00Z
---

# Story 2.6: Verificação de restauração a partir de snapshot

Status: ready-for-dev

## Story

As a Developer/Operator,
I want a verification routine that restores a DB slice from a snapshot and runs basic integrity checks,
so that we can validate that snapshots can be used to recover data.

## Acceptance Criteria

1. Given a snapshot CSV file, when the restore verification runs into a temporary DB, then the restored DB has expected row counts and checksums match.
2. The verification returns pass/fail and logs details (job_id, rows_restored, checksum_ok, errors).
3. The routine can be run locally via CLI for a single snapshot and in CI as a smoke check (mocked or with fixture data).

## Tasks / Subtasks

- [ ] Implement `pipeline.restore_verify --snapshot <path>` CLI command (Typer).
  - [ ] Parse snapshot CSV and compute checksum (SHA256) vs stored metadata.
  - [ ] Create a temporary SQLite DB (e.g., `:memory:` or temp file) and import snapshot rows.
  - [ ] Run integrity checks: row counts, required columns present, sample row checksum, and optional hash of canonicalized rows.
  - [ ] Produce structured JSON report and exit code (0=OK,1=Warn,2=Fail).
- [ ] Add unit tests using fixture snapshot in `tests/fixtures/` and an integration smoke test for CI (mocked providers or small sample CSV).
- [ ] Document runbook in `docs/playbooks/` and add example command to `README.md`.

## Dev Notes

- Use existing snapshot format and metadata conventions from `docs/planning-artifacts/epics.md` (Epic 2: snapshots with checksum SHA256).
- Temporary DB: prefer SQLite `:memory:` for speed in CI; allow `--temp-db /path/to/file` for local inspection.
- Ensure CSV parsing uses canonical column order and types before checksum comparison (normalize whitespace, date formats to ISO8601 UTC).
- Exit codes: 0 = pass, 1 = warning (minor mismatches), 2 = fail (critical mismatch or missing required columns).

### Project Structure Notes

- CLI entrypoint: `src/cli.py` (Typer) → implement `restore_verify` subcommand delegating to `src/etl/snapshot.py` or `src/snapshots/manager.py`.
- Tests: add `tests/test_restore_verify.py` and use `tests/fixtures/sample_snapshot.csv`.
- References for implementation: `docs/planning-artifacts/epics.md` (Epic 2), `docs/planning-artifacts/prd.md` (snapshot requirements), `docs/planning-artifacts/architecture.md` (DB constraints).

### References

- Source: docs/planning-artifacts/epics.md#Story-2.6: Verificação de restauração a partir de snapshot
- PRD: docs/planning-artifacts/prd.md (Snapshot CSV + checksum requirements)
- Architecture: docs/planning-artifacts/architecture.md (DB and persistence guidance)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes

- Created story file from epic context and PRD/architecture artifacts.
- Updated `sprint-status.yaml` to mark story as `ready-for-dev`.
