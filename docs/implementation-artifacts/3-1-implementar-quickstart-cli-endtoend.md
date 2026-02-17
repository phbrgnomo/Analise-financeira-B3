---
story_key: 3-1-implementar-quickstart-cli-endtoend
story_id: 3.1
status: ready-for-dev
created_by: Phbr
created_at: 2026-02-17T00:00:00Z
---

# Story 3.1: Implementar Quickstart CLI end‑to‑end

Status: ready-for-dev

## Story

As a New User,
I want a single command `poetry run main --ticker <TICKER> [--force-refresh]` that executes ingest→persist→snapshot→notebook-run (where applicable),
so that I can reproduce a complete experiment quickly.

## Acceptance Criteria

1. Given a developer machine with dependencies installed
   When the user runs `poetry run main --ticker PETR4.SA --force-refresh`
   Then the pipeline executes ingest (using adapter), persists canonical data, generates snapshot CSV, and returns a success status.

2. The CLI prints a short summary with `job_id`, `elapsed_sec`, `snapshot path` and `rows` to stdout; `--format json` emits the JSON summary for CI consumption.

3. CLI supports operational flags: `--dry-run`, `--no-network`, `--sample-tickers <file|list>`, `--max-days <N>`, `--format json|text` and `--force-refresh`.

4. The command returns semantic exit codes (0=OK,1=Warning,2=Critical) and is usable by CI smoke tests (e.g., `--no-network` with fixtures should exit 0).

5. Snapshot CSV(s) are generated under `snapshots/` with filename pattern `<TICKER>-YYYYMMDD.csv` and companion `.checksum` file with SHA256; CI validates checksum.

6. The quickstart flow writes canonical rows into `dados/data.db` (table `prices`) with upsert semantics by `(ticker, date)`.

## Tasks / Subtasks

- [ ] Task 1: Implement CLI entrypoint and Typer-based command `main --ticker` (AC: 1,2,3)
  - [ ] Subtask 1.1: Add CLI flags and help text; support `--format json` output
  - [ ] Subtask 1.2: Wire CLI to `pipeline.ingest` orchestration function

- [ ] Task 2: Implement quick orchestration `pipeline.ingest` (AC: 1,3,4)
  - [ ] Subtask 2.1: Support `--dry-run`, `--no-network`, `--force-refresh` behavior
  - [ ] Subtask 2.2: Return structured summary (job_id, elapsed_sec, snapshot, rows)

- [ ] Task 3: Integrate adapters + canonical mapper in quickstart path (AC: 1,6)
  - [ ] Subtask 3.1: Use existing Adapter interface and canonical mapper (or provide minimal stubs if missing)

- [ ] Task 4: Snapshot generation and checksum (AC: 5)
  - [ ] Subtask 4.1: Write snapshot CSV under `snapshots/` with metadata and compute SHA256
  - [ ] Subtask 4.2: Write companion `.checksum` file and record metadata in `metadata`/`snapshots` table

- [ ] Task 5: Tests and CI integration (AC: 2,4,5)
  - [ ] Subtask 5.1: Add mocked quickstart integration test using `tests/fixtures/sample_ticker.csv`
  - [ ] Subtask 5.2: Add CI step that runs quickstart in `--no-network` mode and validates produced checksum

## Dev Notes

- Relevant architecture patterns and constraints:
  - Use Typer for CLI entrypoints; prefer `poetry run main` script mapping to `src.main:main`.
  - ETL: adapters → canonical mapper → persistence (SQLite via SQLAlchemy or pandas `to_sql` with upsert semantics).
  - Upsert semantics: implement `INSERT OR REPLACE` / `ON CONFLICT` by `(ticker,date)` to ensure idempotency.
  - Snapshot and raw artifacts: `snapshots/` and `raw/<provider>/` directories; snapshots must include SHA256 checksum and companion `.checksum` file.
  - Permissions: `dados/data.db` and backups should be created with owner-only permissions where applicable.

- Source tree components to touch:
  - `src/main.py` (CLI wiring)
  - `src/dados_b3.py` (data access / DB helpers)
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

## Dev Agent Record

### Agent Model Used

GPT-5 mini (automated BMad run)

### Completion Notes List

- Ultimate context engine analysis completed for quickstart CLI story.

### File List

- docs/implementation-artifacts/3-1-implementar-quickstart-cli-endtoend.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
