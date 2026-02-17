---
generated_by: create-story workflow
story_key: 1-7-implementar-transformacao-de-retornos-e-persistencia-em-returns
story_id: 1.7
status: ready-for-dev
---

# Story 1.7: Implementar transformação de retornos e persistência em returns

Status: ready-for-dev

## Story

As a Data Consumer,
I want a routine that computes daily returns from prices and persists them in the `returns` table,
so that downstream notebooks and modeling code can read precomputed returns.

## Acceptance Criteria

1. Given canonical `prices` stored in DB
   When the `compute_returns()` routine runs for a ticker
   Then daily returns are computed (simple percent change) and persisted to `returns` with `return_type='daily'`.
2. Annualization conventions (252 trading days) are documented in code/comments and used by any annualized conversions.
3. Upsert semantics must be used for `returns` to avoid duplicate rows for (ticker, date, return_type).
4. Provide unit tests covering: single-ticker run, idempotent re-run (no duplicates), handling of missing dates/gaps, and basic numeric sanity checks.
5. Dev notes must include expected table schema, example SQL for upsert, and the preferred implementation approach (pandas -> sqlalchemy/DB API).

## Tasks / Subtasks

- [ ] Implement `compute_returns(ticker: str, start: Optional[date]=None, end: Optional[date]=None)` routine
  - [ ] Load canonical `prices` for ticker via `db.read_prices(ticker, start, end)`
  - [ ] Compute simple daily returns: `return = price.close.pct_change()` (preserve date alignment)
  - [ ] Populate `returns` DataFrame with columns: `ticker, date, return, return_type, created_at`
  - [ ] Upsert into `returns` table by `(ticker, date, return_type)` using `INSERT OR REPLACE` / `ON CONFLICT` semantics
  - [ ] Add telemetry/logging (job_id, rows_written, duration_ms) to `ingest_logs` or `metrics` as appropriate
- [ ] Add unit tests in `tests/` for happy path and edge cases (missing dates, duplicated runs)
- [ ] Add minimal CLI entrypoint: `main compute-returns --ticker <TICKER> [--start] [--end] [--dry-run]`
- [ ] Document annualization and conventions in code comments and `docs/` (reference to `conv_retorno` if exists)

## Dev Notes

- Technical stack: Python, pandas for ETL, SQLAlchemy or `sqlite3` for persistence, use project's DB layer (`src.retorno` / `src.dados_b3` conventions).
- Preferred approach: read canonical `prices` into a DataFrame, compute `pct_change()` on `adj_close` or `close` depending on canonical schema, shift/align to ensure `date` maps to next-day returns if desired (but default: return at day t = (price_t / price_{t-1}) - 1 attached to `date = t`).
- Persist using upsert: for SQLite use `INSERT INTO returns (cols...) VALUES (...) ON CONFLICT(ticker,date,return_type) DO UPDATE SET ...` or `INSERT OR REPLACE` while preserving `created_at` semantics.
- Annualization: use 252 trading days for annualizing volatility/returns; note this in header comments and tests.
- Testing: include numeric tolerance assertions (e.g., close to expected pct change) and idempotency test (running twice writes same rows, no duplicates).

### Project Structure Notes

- Suggested files to touch:
  - `src/retorno.py` (add `compute_returns()` and persistence helpers)
  - `src/dados_b3.py` / DB layer (use `db.read_prices` / `db.write_returns` patterns)
  - `tests/test_returns.py` (unit tests using `tests/fixtures/sample_ticker.csv`)
- Paths: canonical prices in `dados/data.db` (`prices` table); returns persisted to `dados/data.db` (`returns` table).

### References

- Source: docs/planning-artifacts/epics.md#Story-1.7 (Epic 1 definitions)
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

- create-story workflow run: `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`

### Completion Notes List

- Ultimate context engine analysis completed for story 1.7.

### File List

- docs/planning-artifacts/epics.md (source)
- docs/implementation-artifacts/sprint-status.yaml (updated)
