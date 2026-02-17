---
generated: 2026-02-17T00:00:00Z
story_key: 4-4-monitoramento-de-integridade-de-snapshots-ci
story_id: 4.4
status: ready-for-dev
owner: CI / Dev
---

# Story 4.4: Monitoramento de integridade de snapshots (CI)

Status: ready-for-dev

## Story

As a CI Engineer,
I want a job that validates snapshot checksums and alerts on mismatch,
so that snapshot generation/regressions are detected early in PRs.

## Acceptance Criteria

1. Given a snapshot CSV is generated in CI (mocked or sample)
   When the CI validation job runs
   Then it computes the SHA256 checksum and compares with the recorded metadata and fails the job on mismatch

2. The job publishes an artifact with the computed checksum and a short failure report when run.

3. CI validation job publishes both the generated CSV and a `.checksum` artifact and fails on checksum mismatch.

4. The CI job can run in `--no-network` mode using deterministic fixtures under `tests/fixtures/` to compute the expected checksum.

## Tasks / Subtasks

- [ ] Implement CI job workflow (`.github/workflows/checksum-validate.yml`) that:
  - [ ] Runs quickstart snapshot generation using fixtures (`--no-network` or `--use-fixture`).
  - [ ] Computes SHA256 checksum of generated CSV and compares with expected value (metadata or known checksum file).
  - [ ] Publishes artifacts: generated CSV and `.checksum` file and a short failure report on mismatch.
  - [ ] Exits non-zero on mismatch and logs structured summary to stdout (JSON) for CI parsing.
- [ ] Add unit/integration tests under `tests/` that:
  - [ ] Provide deterministic fixtures in `tests/fixtures/` for snapshot generation.
  - [ ] Validate checksum computation routine against fixture CSVs.
- [ ] Add helper command in CLI (e.g., `main snapshots verify --file <path>`) to compute and print checksum and verification result.
- [ ] Document run and expected artifacts in `docs/operations/runbook.md` and README quickstart.

## Dev Notes

- Technical requirements: use SHA256 for checksum; record checksum in metadata (e.g., companion `.checksum` file or metadata DB table). Compute checksum using streaming read to support large files.
- CI considerations: job must be able to run without network using `--no-network` fixtures; publish artifacts for debugging on failure.
- Exit codes: 0 = OK, 1 = Warning (e.g., minor mismatch threshold?), 2 = Critical (checksum mismatch).
- File locations: snapshots written to `snapshots/` in CI run; published artifacts should include `snapshots/<name>.csv` and `snapshots/<name>.csv.checksum`.

### Project Structure Notes

- Suggested CI workflow path: `.github/workflows/checksum-validate.yml`.
- Suggested CLI helper: integrate into existing `main` Typer commands, e.g., `main snapshots verify --file path --expected-checksum file`.
- Tests: `tests/fixtures/` must include at least one deterministic CSV used by CI to validate checksum computation.

### References

- Source: docs/planning-artifacts/epics.md#Story-4.4 (Epic 4 — Operações & Observabilidade)
- CI artifact conventions: publish CSV and companion `.checksum` file

## Dev Agent Record

### Agent Model Used
GPT-5 mini (automated story generator)

### Completion Notes List

- Story file created from template and epics analysis.
- Sprint status updated: story marked `ready-for-dev`.

### File List

- docs/implementation-artifacts/4-4-monitoramento-de-integridade-de-snapshots-ci.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
