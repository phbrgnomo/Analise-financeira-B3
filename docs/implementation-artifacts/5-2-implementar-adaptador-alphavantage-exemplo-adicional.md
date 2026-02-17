---
story_key: 5-2-implementar-adaptador-alphavantage-exemplo-adicional
epic: 5
story_num: 2
title: Implementar adaptador AlphaVantage (exemplo adicional)
status: ready-for-dev
created_by: Phbr
created_at: 2026-02-17T00:00:00Z
---

# Story 5.2: Implementar adaptador AlphaVantage (exemplo adicional)

Status: ready-for-dev

## Story

As a Developer,
I want a working AlphaVantage adapter that returns raw provider DataFrames,
so that the system supports at least two independent providers for redundancy.

## Acceptance Criteria

1. Given an API key or `--no-network` fixture, when the adapter is invoked for `PETR4.SA`, then it returns a raw `pandas.DataFrame` with provider-specific columns and `source='alphavantage'`.
2. The adapter supports retries/backoff honoring `ADAPTER_MAX_RETRIES` and logs attempts to `ingest_logs` with fields: `job_id`, `provider`, `attempt`, `status_code`, `retry_after` (if present).
3. Adapter implements a `--use-fixture` / `--no-network` mode for CI and local testing (uses `tests/fixtures/providers/alphavantage/...`).
4. Adapter saves raw response CSV to `raw/alphavantage/<ticker>-<ts>.csv` and records `raw_checksum` (SHA256) and `fetched_at` in metadata when persistence is enabled.
5. Adapter documents expected raw columns and any necessary transformations in `docs/planning-artifacts/adapter-mappings.md` (row example included).

## Tasks / Subtasks

- [ ] Implement adapter module: `src/adapters/alphavantage_adapter.py` with class `AlphaVantageAdapter(Adapter.v1)` exposing `fetch(ticker, use_fixture=False)`.
  - [ ] Support API key from env var `ALPHAVANTAGE_API_KEY` (via `.env` / `python-dotenv`) and `config/providers.yaml` loader (pydantic model).
  - [ ] Implement retries with exponential backoff + jitter; respect `Retry-After` when present.
  - [ ] Implement `--use-fixture` mode that loads stored response JSON/CSV from `tests/fixtures/providers/alphavantage/`.
  - [ ] Save raw CSV to `raw/alphavantage/` with UTC timestamp and compute SHA256 checksum (use `src/utils/checksums.py`).
- [ ] Add contract tests: `tests/adapters/test_alphavantage_contract.py` (mode: fixture/no-network) verifying returned columns, presence of `source` and `fetched_at`, retry behaviour.
- [ ] Update `docs/planning-artifacts/adapter-mappings.md` with AlphaVantage mapping example (raw → canonical) and example raw row.
- [ ] Add provider entry to `config/providers.example.yaml` with timeouts, priority and `use_fixture` example.
- [ ] Add minimal README snippet in `docs/implementation-artifacts/5-2-implementar-adaptador-alphavantage-exemplo-adicional.md` (this file) referencing usage examples and CLI invocation.

## Dev Notes

- Follow architecture decisions in `docs/planning-artifacts/architecture.md`:
  - Use `pandas` for raw parsing and `pandera` for post-normalization validation.
  - Persist raw CSVs in `raw/alphavantage/` and generate `raw_checksum` (SHA256).
  - Use `SQLAlchemy` DB layer helpers (`src/db/db.py`) for ingest logging `ingest_logs` and job metadata.
- Implementation patterns:
  - Module path: `src/adapters/alphavantage_adapter.py` (conform to `src/adapters/` layout).
  - Class name: `AlphaVantageAdapter` implementing `Adapter.v1` contract: `fetch(ticker, use_fixture=False) -> pd.DataFrame`
  - Logging: structured JSON with `job_id` and attempt metadata; integrate with existing logging conventions.
  - Tests: ensure `--no-network`/fixture mode used in CI; include sample fixture under `tests/fixtures/providers/alphavantage/PETR4_sample.json` or CSV.

### Project Structure Notes

- Suggested files to touch:
  - `src/adapters/alphavantage_adapter.py`
  - `src/utils/checksums.py` (if not present)
  - `tests/adapters/test_alphavantage_contract.py`
  - `config/providers.example.yaml`
  - `docs/planning-artifacts/adapter-mappings.md`

### References

- Source epic/story: docs/planning-artifacts/epics.md#Epic-5—Adaptadores-&-Normalização
- Architecture constraints: docs/planning-artifacts/architecture.md
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml
- Adapter mappings target: docs/planning-artifacts/adapter-mappings.md

## Dev Agent Record

### Agent Model Used
GPT-5 mini

### Completion Notes List

- Story file created from template and epic analysis.
- Acceptance criteria and tasks extracted from `epics.md` and aligned with architecture guidance.

### File List

- src/adapters/alphavantage_adapter.py (suggested)
- tests/adapters/test_alphavantage_contract.py (suggested)
- docs/planning-artifacts/adapter-mappings.md (updated)
