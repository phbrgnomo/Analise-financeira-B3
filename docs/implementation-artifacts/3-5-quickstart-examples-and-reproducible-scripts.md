---
story_key: 3-5-quickstart-examples-and-reproducible-scripts
epic: 3
story_num: 5
title: Quickstart examples and reproducible scripts
status: ready-for-dev
created_by: Phbr
created_at: 2026-02-17T00:00:00Z
---

# Story 3.5: Quickstart examples and reproducible scripts

Status: ready-for-dev

## Story

As a New Contributor,
I want example scripts and commands that reproduce the quickstart for sample tickers,
so that I can validate the environment and understand expected outputs.

## Acceptance Criteria

1. Given a fresh checkout and dependencies installed
   When the developer runs `examples/run_quickstart_example.sh`
   Then the example executes the quickstart for a sample ticker, generates a snapshot in `snapshots/` and writes a short run log to `logs/`.
2. The example script documents expected run time and outputs in comments and exits with non-zero on failures to enable CI detection.
3. The example supports `--config` or respects `ENV` vars and writes artifacts to `outputs/` by default.
4. Script uses `--no-network` / fixtures (`tests/fixtures/sample_ticker.csv`) for CI determinism.

## Tasks / Subtasks

- [ ] Create `examples/run_quickstart_example.sh` (executable) that runs the quickstart using fixtures
  - [ ] Implement `--no-network` invocation to use `tests/fixtures/sample_ticker.csv`
  - [ ] Write short run log to `logs/` and artifacts to `outputs/`/`snapshots/`
- [ ] Add README section with copy-paste example and expected JSON/text summary
- [ ] Add CI smoke job example (or instructions) that runs the example script and validates exit code and artifact presence
- [ ] Add simple integration test (pytest) that executes the script in a controlled tempdir and asserts snapshot + log created

## Dev Notes

- Example command (CI-friendly):

  ```bash
  examples/run_quickstart_example.sh --no-network --ticker PETR4.SA --format json
  ```

- The script should default to writing outputs to `outputs/` and snapshots to `snapshots/`, and logs to `logs/`.
- The script must accept `--config` or environment variables (e.g., `DATA_DIR`, `SNAPSHOT_DIR`, `OUTPUTS_DIR`).
- When using fixtures, pass `--sample-tickers tests/fixtures/sample_ticker.csv` to the CLI to avoid external calls.

### Project Structure Notes

- Add `examples/run_quickstart_example.sh` (shell script) at repository root `examples/`.
- Ensure `examples/` is included in repository and executable bit set.
- CI pipelines should be able to call the script from repo root.

### Technical Requirements / Guardrails

- Must run using project CLI entrypoint: `poetry run main --no-network --ticker <TICKER> --format json`
- Script must exit non-zero on failures and print a short JSON summary when `--format json` provided, e.g.:

  ```json
  {"job_id":"<uuid>","status":"success","elapsed_sec":12,"snapshot":"snapshots/PETR4-20260215.csv","rows":42}
  ```

- Respect environment defaults from project (see `docs/planning-artifacts/epics.md`): `DATA_DIR=./dados`, `SNAPSHOT_DIR=./snapshots`, `OUTPUTS_DIR=./outputs`, `LOG_DIR=./logs`.
- When writing files, ensure deterministic filenames for CI (timestamp can be included but tests should assert presence via glob pattern).

### Testing Requirements

- Add a pytest that executes the example script in a tmpdir with `--no-network` and asserts:
  - snapshot file exists under `snapshots/` or `outputs/`
  - a run log exists under `logs/` containing `job_id` and `status`
  - script exits with code 0 on success
- CI job should run the script with `--no-network` and publish generated snapshot + `.checksum` as artifacts for inspection.

### References

- Source: docs/planning-artifacts/epics.md#Epic-3 — Story 3.5 definition and acceptance criteria
- Related examples & fixtures: tests/fixtures/sample_ticker.csv

## Dev Agent Record

### Agent Model Used

GPT-generated artifact (assistant automation)

### Completion Notes

- Created `examples/run_quickstart_example.sh` (skeleton) — TODO: implement CLI invocation and fixture wiring
- Updated `docs/implementation-artifacts/sprint-status.yaml` to mark story ready-for-dev

### File List

- examples/run_quickstart_example.sh (new, executable)
- docs/implementation-artifacts/3-5-quickstart-examples-and-reproducible-scripts.md (this file)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
