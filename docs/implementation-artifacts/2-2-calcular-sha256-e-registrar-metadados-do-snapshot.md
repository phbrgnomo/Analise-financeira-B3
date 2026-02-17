---
story_key: 2-2-calcular-sha256-e-registrar-metadados-do-snapshot
epic: 2
story_id: 2.2
status: ready-for-dev
owner: Dev / Operator
created_at: 2026-02-17T00:00:00Z
---

# Story 2.2: Calcular SHA256 e registrar metadados do snapshot

Status: ready-for-dev

## Story

As an Operator,
I want the snapshot process to compute a SHA256 checksum for each generated CSV and store metadata,
so that CI and downstream processes can verify snapshot integrity.

## Acceptance Criteria

1. Given a snapshot CSV is generated
   When the snapshot finalization step runs
   Then a SHA256 checksum is computed and recorded in the `snapshots` metadata table (created_at, rows, checksum, job_id)
   And the checksum file or metadata is stored alongside the CSV.

## Tasks / Subtasks

- [ ] Implement checksum computation (SHA256) for snapshot files (binary file bytes, UTF-8, no transformations)
  - [ ] Produce `<snapshot>.sha256` file next to CSV containing the hex checksum and filename
  - [ ] Ensure computation is deterministic (explicit encoding and newline handling)
- [ ] Persist metadata record to DB table `snapshots` (or `metadata`) with fields: `id`, `ticker`, `snapshot_path`, `created_at`, `rows`, `checksum`, `job_id`
- [ ] Add an idempotent finalization step that: writes checksum file, inserts/updates metadata row, and returns structured summary (job_id, snapshot, rows, checksum)
- [ ] Add unit tests for checksum function (including edge cases: empty file, large files)
- [ ] Add integration test that generates a small snapshot, runs finalization, and validates DB metadata + checksum file
- [ ] Update CI job to validate snapshot checksum against stored metadata for sample snapshots (see FR37)
- [ ] Add docs snippet in `docs/phase-1-report.md` and `docs/playbooks/quickstart-ticker.md` describing verification steps and artifacts

## Dev Notes

- File locations and patterns:
  - Snapshots directory: `snapshots/` (repo-root)
  - Snapshot filename pattern: `<ticker>-YYYYMMDD.csv` (UTC date) or `<ticker>-YYYYMMDDTHHMMSSZ.csv` if timestamped
  - Checksum file pattern: `<snapshot>.sha256` stored alongside CSV
  - DB: `dados/data.db` with table `snapshots` (or `metadata`) persisted by SQLAlchemy/DB layer

- Suggested DB schema (example):

  - Table `snapshots` (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    snapshot_path TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    rows INTEGER NOT NULL,
    checksum TEXT NOT NULL,
    job_id TEXT
  )

- Checksum computation guidance:
  - Compute SHA256 over raw file bytes (open file in binary mode)
  - Do not alter file content (no newline normalization)
  - Use a stable chunked read for large files (e.g., 64KB chunks)
  - Produce checksum file containing: `<hex-checksum>  <filename>` (two spaces or single space acceptable; document the format)

- Idempotency and safety:
  - When running finalization multiple times, ensure metadata upsert semantics (INSERT ON CONFLICT DO UPDATE) to avoid duplicates
  - Ensure atomicity: write checksum file to a temp name then rename atomically; persist DB record after checksum file is present
  - Use a generated `job_id` (UUID) for traceability; include in logs and metadata

- Testing and CI:
  - Unit tests for `compute_checksum(path)` covering empty and binary contents
  - Integration test that writes a small CSV to `snapshots/test-TESTER-20260215.csv`, runs finalization, asserts
    - `snapshots/test-TESTER-20260215.csv.sha256` exists and matches computed checksum
    - DB entry exists with matching checksum and correct `rows` count
  - Add a CI check step (smoke) that runs a mocked snapshot finalization and validates checksum writing and metadata update (see FR37)

## Project Structure Notes

- Keep implementation code in `src/` following existing patterns (e.g., `src.pipeline.snapshot`, `src.db.snapshots`)
- Expose a CLI hook: `poetry run main snapshot finalize --path <snapshot.csv> --job-id <uuid>` which performs checksum + metadata registration
- Avoid adding new top-level scripts; integrate with existing `pipeline`/`snapshots` modules

## References

- Epic & acceptance criteria: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md)
- Sprint tracking: [docs/implementation-artifacts/sprint-status.yaml](docs/implementation-artifacts/sprint-status.yaml)

## Dev Agent Record

### Agent Model Used

automated-agent

### Completion Notes List

- Created story file from template and epic source (2026-02-17)

### File List

- snapshots/ (target directory for generated artifacts)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
