## Story 4.3: Backup & Restore operacional

Status: ready-for-dev

## Story

As an Operator,
I want commands to create and restore backups of `dados/data.db` and verify integrity,
so that I can perform recoveries and validate backups in test runs.

## Acceptance Criteria

1. Given the system has canonical data in `dados/data.db`, when the operator runs `poetry run main backup --create --out backups/backup-YYYYMMDD.db` or `poetry run main backup --restore --from backups/backup-YYYYMMDD.db`, then the backup is created (copied) and the restore verification routine loads the backup into a temporary DB and runs basic integrity checks (row counts, checksum match).
2. Backups are created atomically (write-to-temp + rename) and a checksum (SHA256) is computed and written to a companion `.checksum` file.
3. Created backup files receive owner-only permissions (`chmod 600`) by default after creation.
4. The `backup --create` command supports `--verify` which runs the restore verification automatically and returns non-zero on verification failure.
5. Backup/restore operations are logged with `job_id` and reported in the CLI summary. Exit codes must be semantic (0=OK, 1=Warning, 2=Critical) for automation.

## Tasks / Subtasks

- [ ] Implement `main backup --create --out <path>`: write-to-temp + rename, compute SHA256, write `<file>.checksum`, set `chmod 600`.
  - [ ] Subtask: Choose atomic write pattern and implement safe rename.
  - [ ] Subtask: Compute SHA256 and write companion `.checksum` file.
  - [ ] Subtask: Ensure file permissions set to owner-only after write.
- [ ] Implement `main backup --restore --from <path>`: copy/attach backup to temporary DB and run integrity checks (row counts, basic query smoke tests).
  - [ ] Subtask: Implement temp DB load and verification routine.
  - [ ] Subtask: Provide `--yes`/`--dry-run` flags for safe restores.
- [ ] Add `--verify` flag to `backup --create` that automatically runs restore verification and fails on mismatch.
- [ ] Add logging with `job_id` for both create and restore operations and ensure structured JSON logs include (`ticker` optional, `job_id`, `started_at`, `finished_at`, `rows`, `checksum`, `status`, `error_message`).
- [ ] Add CLI tests (unit/integration mocked) under `tests/` to validate backup create, checksum generation, and restore verification (use fixtures/no-network where applicable).
- [ ] Document runbook steps in `docs/operations/runbook.md` and add examples in README quickstart.

## Dev Notes

- Backup file pattern: `backups/backup-<YYYYMMDDTHHMMSSZ>.db` and companion `backups/backup-<ts>.db.checksum` (SHA256).
- Atomic write: write to `backups/.tmp-<name>`, fsync, then `os.rename()` to final path to avoid partial writes.
- Verification: open restored DB in temporary location, run quick smoke queries (e.g., `SELECT COUNT(1) FROM prices; SELECT COUNT(1) FROM returns;`) and compare row counts with metadata recorded at backup time.
- Integrity: compute SHA256 of final backup file and compare with recorded value; if mismatch, fail verification and log details.
- Permissions: after successful write, run `os.chmod(path, 0o600)` to set owner-only permissions.
- Logging: use structured JSON logs and include `job_id` (UUIDv4), timestamps in UTC ISO8601, and `duration_ms`.
- CI: add deterministic fixture(s) in `tests/fixtures/` to allow checksum validation in `--no-network` mode.

### Project Structure Notes

- Backups should live under `backups/` at repo root (configurable via `BACKUP_DIR` env). Default `BACKUP_DIR=./backups`.
- DB path configured via `DATA_DIR` env (default `./dados`) and `dados/data.db` used as canonical DB default.
- Commands implemented in CLI entrypoint (`src/main.py` / `pipeline` module) following existing Typer patterns.

### References

- Source epic and story definition: docs/planning-artifacts/epics.md (Epic 4 — Operações & Observabilidade, Story 4.3)
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Story created from epic context (Epic 4) and sprint tracking entry.

### File List

- docs/implementation-artifacts/4-3-backup-restore-operacional.md
