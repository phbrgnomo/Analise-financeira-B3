## Story 2.4: ci-validation-job-para-checar-checksums-de-snapshots

Status: ready-for-dev

## Story

As a CI Engineer,
I want a CI job that valida generated snapshot checksums and compares them with recorded metadata,
so that pull requests that touch snapshot generation or snapshot metadata fail in controlled tests when checksums mismatch.

## Acceptance Criteria

1. Given a test snapshot is generated in CI (mocked or small sample), when the CI validation step runs, then the job computes the SHA256 checksum and compares with the expected value and fails on mismatch.
2. The CI job exposes logs and artifacts (CSV + .checksum or metadata) for failed comparisons to aid debugging.
3. The job supports running against a mocked snapshot in CI (`--no-network` / fixtures) and returns semantic exit codes (0=OK,1=Warning,2=Critical) so pipelines can act on results.
4. CI step publishes the snapshot artifact and a `.checksum` (or metadata JSON) alongside logs when run in CI.

## Tasks / Subtasks

- [ ] Implement `ci/validate_snapshot_checksums` job in CI (GitHub Actions) that:
  - [ ] runs unit/integration fixture to produce a snapshot (or consumes pre-generated fixture snapshot)
  - [ ] computes SHA256 checksum (via `sha256sum` or Python `hashlib.sha256`) for the snapshot CSV
  - [ ] compares computed checksum with expected checksum from metadata file or database
  - [ ] fails the job on mismatch and uploads artifacts (snapshot.csv, snapshot.csv.checksum, logs)
  - [ ] returns semantic exit codes and prints JSON summary when `--format json` is requested
- [ ] Add test fixture snapshot and expected `.checksum` file in `tests/fixtures/` for CI smoke
- [ ] Add small integration test that runs `poetry run main --no-network --ticker PETR4.SA --format json` and verifies checksum validation step exits 0
- [ ] Update `.github/workflows/ci.yml` to include the validation step after snapshot generation steps (use fixture path and artifact publishing)

## Dev Notes

- Snapshot location: `snapshots/` (project root) — CI should locate snapshots there or use artifacts published by pipeline step.
- Checksum algorithm: SHA256 (hex lowercase)
- Metadata sources: `snapshots` metadata table (DB) OR a sidecar `<snapshot>.checksum` file next to CSV. CI must support both.
- Recommended approach: CI step should accept either a path to a `.checksum` file or a metadata JSON; prefer file-based `.checksum` for simplicity in lightweight CI.
- For reproducible CI: run snapshot generation with `--no-network` and deterministic fixtures in `tests/fixtures/`.
- Exit codes: 0 = checksums match; 2 = mismatch/failure; 1 = warning/partial match or non-fatal inconsistencies.
- Artifact publishing: upload `snapshot.csv`, `snapshot.csv.checksum`, and a small validation report `snapshot-validation.json` with fields: `job_id`, `snapshot_path`, `expected_checksum`, `computed_checksum`, `result`.

### Implementation hints

- Use Python script `scripts/ci_validate_checksums.py` to compute and compare checksums; example usage:

  ```bash
  python scripts/ci_validate_checksums.py --snapshot snapshots/PETR4-20260215.csv --expected-file snapshots/PETR4-20260215.csv.checksum --format json
  ```

- Minimal Python check (example snippet):

  ```python
  import hashlib
  h = hashlib.sha256()
  with open(snapshot_path,'rb') as f:
      for chunk in iter(lambda: f.read(8192), b''):
          h.update(chunk)
  print(h.hexdigest())
  ```

### Testing Requirements

- Unit test for `scripts/ci_validate_checksums.py` that computes checksum of a small fixture and asserts equality with provided `.checksum` file.
- Integration CI step uses `--no-network` fixture to generate snapshot and then runs validation step; job fails on mismatch and uploads artifacts.

### Project Structure Notes

- CI job: `.github/workflows/ci.yml` — add `validate-snapshots` job or step in existing workflow after snapshot generation.
- Fixtures: `tests/fixtures/sample_snapshot.csv` and `tests/fixtures/sample_snapshot.csv.checksum`.
- Script: `scripts/ci_validate_checksums.py` (small utility, cross-platform) or use `sha256sum` on Linux runners.

### References

- Source: docs/planning-artifacts/epics.md#Epic-2-Snapshots-&-Exportação
- Acceptance criteria: docs/planning-artifacts/epics.md (Story 2.4)

## Dev Agent Record

### Agent Model Used
internal-assistant

### Completion Notes List

- Story file generated from template and epic context.
- Sprint status updated to `ready-for-dev`.

### File List

- docs/planning-artifacts/epics.md
- docs/implementation-artifacts/2-4-ci-validation-job-para-checar-checksums-de-snapshots.md
