---
story_key: 3-1-implementar-quickstart-cli-endtoend
story_id: 3.1
status: ready-for-dev
created_by: Phbr
created_at: 2026-02-17T00:00:00Z
---

# Story 3.1: Implementar Quickstart CLI end‑to‑end

Status: ready-for-review

## Story

As a New User,
I want a single command `poetry run main --ticker <TICKER> [--force-refresh]` that runs the core pipeline (ingest→persist→snapshot) by default, and optionally executes the analysis notebook when called with `--run-notebook`,
so that I can reproduce a complete experiment quickly while keeping notebook execution opt-in.

## Acceptance Criteria

1. Given a developer machine with dependencies installed
   When the user runs `poetry run main --ticker PETR4 --force-refresh`
   Then the pipeline executes ingest (using adapter), persists canonical data, generates snapshot CSV, and returns a success status.

2. The CLI prints a short summary with `job_id`, `elapsed_sec`, `snapshot path` and `rows` to stdout; `--format json` emits the JSON summary for CI consumption.

3. CLI supports operational flags: `--dry-run`, `--no-network`, `--sample-tickers <file|list>`, `--max-days <N>`, `--format json|text` and `--force-refresh`.

4. The command returns semantic exit codes (0=OK,1=Warning,2=Critical) and is usable by CI smoke tests (e.g., `--no-network` with fixtures should exit 0).

5. Snapshot CSV(s) are generated under `snapshots/` with filename pattern `<TICKER>-YYYYMMDD.csv` and companion `.checksum` file with SHA256; CI validates checksum.

6. The quickstart flow writes canonical rows into `dados/data.db` (table `prices`) with upsert semantics by `(ticker, date)`.

7. The CLI supports an optional `--run-notebook` flag that, when provided, runs papermill after the core pipeline (ingest→persist→snapshot) completes.

## Tasks / Subtasks

- [x] Task 1: Refactor the existing command `poetry run main run` for the desired entrypoint with `main --ticker` and operational flags (AC: 1,2,3)
  - [x] Subtask 1.1: Add CLI flags and help text; support `--format json` output
  - [x] Subtask 1.2: Verify the CLI wiring to `pipeline.ingest` orchestration function
  - [x] Subtask 1.3: Implement optional `--run-notebook` flag that triggers papermill after the core pipeline (`poetry run main --ticker <TICKER> [--force-refresh]`) completes

- [x] Task 2: Verify the implementation of the quick orchestration `pipeline.ingest` through the command `poetry run pipeline ingest --ticker <TICKER> [--force-refresh]` (AC: 1,3,4)
  - [x] Subtask 2.1: Support `--dry-run`, `--no-network`, `--force-refresh` behavior
  - [x] Subtask 2.2: Return structured summary (job_id, elapsed_sec, snapshot, rows)

- [x] Task 3: Integrate adapters + canonical mapper in quickstart path (AC: 1,6)
  - [x] Subtask 3.1: Use existing Adapter interface and canonical mapper (or provide minimal stubs if missing)

- [x] Task 4: Snapshot generation and checksum (AC: 5)
  - [x] Subtask 4.1: Write snapshot CSV under `snapshots/` with metadata and compute SHA256
  - [x] Subtask 4.2: Write companion `.checksum` file and record metadata in `metadata`/`snapshots` table

- [x] Task 5: Tests and CI integration (AC: 2,4,5)
  - [x] Subtask 5.0: Evaluate existing tests: `tests/test_cli.py`, `tests/integration/test_quickstart_mocked.py` (if exists) and identify gaps in coverage for new flags and snapshot generation.
  - [x] Subtask 5.1: Add mocked quickstart integration test using `tests/fixtures/sample_ticker.csv`
  - [x] Subtask 5.2: Add CI step that runs quickstart in `--no-network` mode and validates produced checksum
  - [x] Subtask 5.3: Integration tests for `poetry run main --ticker` + JSON Summary might be missing. Check existing tests and add an E2E test that runs the command with `--no-network` and validates JSON output + exit code (CI).
  - [x] Subtask 5.4: Add unit tests invoking entrypoint functions `src/main.py` and `src/ingest/pipeline.py` to assert exit codes, JSON summary when using `--format json`, and `--dry-run` and `--force-refresh` behavior.

- [x] Task 6: Document implemented features, usage examples and rationale in `docs/sprint-reports/3-1-quickstart-cli.md`.
  - [x] Update `docs/playbooks/quickstart-ticker.md` with the final commands.

## Dev Notes

- Relevant architecture patterns and constraints:
  - Use Typer for CLI entrypoints; prefer `poetry run main` script mapping to `src.main:main`.
  - ETL: adapters → canonical mapper → persistence (SQLite via SQLAlchemy or pandas `to_sql` with upsert semantics).
  - Upsert semantics: implement `INSERT OR REPLACE` / `ON CONFLICT` by `(ticker,date)` to ensure idempotency.
  - Snapshot and raw artifacts: `snapshots/` and `raw/<provider>/` directories; snapshots must include SHA256 checksum and companion `.checksum` file.
  - Permissions: `dados/data.db` and backups should be created with owner-only permissions where applicable.
  - DB tests: `tests/test_db_write.py` (existing)
  - Pipeline CLI tests: `tests/test_pipeline_cli.py` (existing)
  - Fixtures: `tests/fixtures/sample_ticker.csv` (existing) for deterministic testing without network.

- Source tree components to touch:
  - `src/main.py` (CLI wiring)
  - `src/ingest/pipeline.py` (orquestração de ingest e persistência)
  - `src/retorno.py` (returns computation if used in quickstart)
  - `tests/` (add integration mocked test using `tests/fixtures/sample_ticker.csv`)

- Testing standards summary:
  - Add an integration test that runs quickstart with `--no-network` and expects exit 0 and JSON summary.
  - Unit tests for snapshot checksum computation and DB upsert behavior.

### Project Structure Notes

- Alignment with repo conventions: follow `src.` package modules, keep CLI in `src/main.py` and helpers in `src/`.
- Detected dependencies: `pandas`, `sqlalchemy`, `typer`, `python-dotenv`, `pytest` (already present in pyproject). Use `pandera` for data validation where appropriate.

### References

- Source: docs/planning-artifacts/epics.md#Epic-3 (Story 3.1 acceptance criteria and notes)
- Source: docs/planning-artifacts/prd.md (Quickstart journeys, technical constraints)
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml
- Implemented features playbooks: docs/playbooks/

## Dev Agent Record

### Completion Notes List

- Added new CLI flags for `--dry-run`, `--sample-tickers`, `--max-days` and `--run-notebook`.
- Updated CLI to emit structured summary including `job_id`, `duration_sec`, `snapshot_path` and `rows` in both text and JSON modes.
- Implemented snapshot filename pattern `<TICKER>-YYYYMMDD.csv` and updated snapshot regex/tests accordingly.
- Added tests covering new CLI flags, sample ticker lists, max-days handling, and JSON output.

### File List

- src/main.py
- src/ingest/pipeline.py
- src/etl/snapshot.py
- tests/test_cli.py
- tests/test_snapshot_regex.py

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/129
