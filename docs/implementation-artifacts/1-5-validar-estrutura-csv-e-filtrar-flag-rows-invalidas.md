# Story 1.5: Validar estrutura CSV e filtrar/flag rows inválidas

Status: ready-for-dev

## Story

As a Data Engineer,
I want the pipeline to validate incoming CSVs against a minimal schema and flag invalid rows,
so that only valid rows enter the canonical pipeline and invalid rows are traceable.

## Acceptance Criteria

1. Given a raw `DataFrame` from the adapter
   When the validator runs
   Then rows not matching the schema are flagged and written to `ingest_logs` with reason codes.
2. A validation summary (`rows_valid`, `rows_invalid`) is returned and logged after each ingest.
3. The pipeline aborts the ingest if invalid rows exceed a default tolerance threshold of 10% (configurable via env var `VALIDATION_INVALID_PERCENT_THRESHOLD`).
4. Invalid rows are persisted (CSV and/or DB) with clear reason codes and a trace to source raw file and row index.
5. Provide unit tests covering: fully valid file, file with <10% invalid rows (passes), file with >=10% invalid rows (aborts), and edge cases (empty file, missing columns).

## Implementation Status

Status: done

Summary of what was delivered against the Acceptance Criteria:

- Validation API: `validate_dataframe(df, schema)` returns `(valid_df, invalid_df, summary)` and `validate_and_handle(...)` performs validation, persistence of invalid rows, logging and threshold enforcement.
- Persistence & Logging: invalid rows written to `raw/<provider>/invalid-<ticker>-<ts>.csv` and referenced in `metadata/ingest_logs.json` with `reason_code`, `reason_message`, `row_index` and `created_at`.
- Threshold: default 10% enforced; configurable via `VALIDATION_INVALID_PERCENT_THRESHOLD` and CLI flag `--validation-tolerance`.
- Tests: unit tests added and adjusted — `tests/test_validation.py`, `tests/test_validation_persistence.py`, and `tests/test_validation_normalize.py` cover key scenarios.
- CLI: `src/main.py` accepts `--validation-tolerance` and propagates it into the pipeline.

All unit tests pass locally (`poetry run pytest` at implementation time).

## Tasks / Subtasks

- [x] Implement `validation` module with `validate_dataframe(df, schema) -> (valid_df, invalid_df, summary)`
  - [x] Define `pandera` schema (or equivalent) for canonical columns as persisted in `docs/schema.json` (e.g.: `ticker, date, open, high, low, close, volume, source, fetched_at`).
    - Nota: `adj_close` é opcional no mapper para cálculos internos; atualize `docs/schema.json` e a validação se for necessário persistir `adj_close`.
  - [x] Map provider raw columns to canonical names prior to validation (use existing `canonical mapper` when available)
- [x] Implement logging into `ingest_logs` for invalid rows with fields: `ticker, source, raw_file, row_index, reason_code, reason_message, job_id, created_at`
- [x] Persist invalid rows to `raw/<provider>/invalid-<ticker>-<ts>.csv` (or a dedicated `invalid/` folder) with checksum and reference in `ingest_logs`
- [x] Expose configurable env var `VALIDATION_INVALID_PERCENT_THRESHOLD` (default `0.10`) and ensure it can be overridden
- [x] Add CLI flag `--validation-tolerance` to `pipeline.ingest` (optional, falls back to env var)
- [x] Add unit/integration tests in `tests/` exercising validator behavior and thresholds
- [x] Document the validator usage and configuration in `docs/playbooks/quickstart-ticker.md` and `docs/phase-1-report.md`
- [x] Documentar o que foi implantado nessa etapa em `docs/sprint-reports` conforme definido no FR28 (`docs/planning-artifacts/prd.md`)

## Dev Notes

- Recommended libs: `pandera` for DataFrame schema validation; `pydantic` for configuration DTOs; `pandas` for ETL.
- Validation should run after canonical mapping and before DB upsert.
- Write invalid rows to a timestamped CSV and record `raw_checksum` and `invalid_checksum` (SHA256) for auditability.
- Schema must tolerate reasonable timezone/format variance for `date` column (normalize to UTC ISO8601 prior to validation).
- Provide clear reason codes (e.g., `MISSING_COL`, `BAD_DATE`, `NON_NUMERIC_PRICE`, `NEGATIVE_VOLUME`) so downstream tooling can aggregate failure metrics.
- Default threshold: 10% invalid → abort ingest if invalid rows / total_rows >= threshold. Make threshold configurable.
- Emit structured JSON log entry summarizing validation results and include `job_id`, `ticker`, `rows_total`, `rows_valid`, `rows_invalid`, `invalid_percent`, `error_codes_count`.
- Tests: use `tests/fixtures/sample_ticker.csv` and add an `invalid_sample.csv` fixture exercising common failure modes.

### Project Structure Notes

- Suggested locations:
  - Validation code: `src/validation.py` or `src/ingest/validation.py`
  - Ingest logging helper: reuse/extend current logging in `src/dados_b3.py` or create `src/ingest/logging.py`
  - Tests: `tests/test_validation.py` and fixtures under `tests/fixtures/`

### References

- Source: docs/planning-artifacts/epics.md#story-1.5
- Related artifacts: docs/planning-artifacts/adapter-mappings.md, docs/planning-artifacts/implementation-readiness-report-2026-02-16.md

## Dev Agent Record

### Agent Model Used
GPT-5 mini

### Completion Notes List

- Story file created and marked `ready-for-dev`.

### File List

- docs/implementation-artifacts/1-5-validar-estrutura-csv-e-filtrar-flag-rows-invalidas.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/118
