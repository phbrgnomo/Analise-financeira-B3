````markdown
# Story 2.1: Gerar snapshot CSV a partir de dados persistidos

Status: ready-for-dev

## Story

As a User,
I want the system to generate a snapshot CSV for a ticker from the canonical `prices` table,
so that I can export a stable copy of the data for analysis and archival.

## Acceptance Criteria

1. Given canonical `prices` exist in `dados/data.db` for a ticker
   When the user runs `pipeline.snapshot --ticker PETR4.SA --date 2026-02-15`
   Then a CSV is written to `snapshots/<TICKER>-YYYYMMDD.csv` containing the canonical rows for that date range
   And snapshot metadata (created_at, rows, source_version) is returned.

## Tasks / Subtasks

- [ ] Implement CLI entry `pipeline.snapshot` (Typer) with flags: `--ticker`, `--date`, `--out`, `--force`.
  - [ ] Parse date range and validate ticker exists in DB.
  - [ ] Query canonical `prices` from `dados/data.db` via DB layer (`db.read_prices(ticker, start, end)`).
- [ ] Implement CSV writer to `snapshots/` with filename pattern `<TICKER>-YYYYMMDD.csv` and owner-readable file permissions.
- [ ] Return snapshot metadata (created_at, rows, source_version) to stdout / return object.
- [ ] Add unit tests using `tests/fixtures/sample_ticker.csv` and an in-memory SQLite to validate CSV contents and row counts.
- [ ] Add a small integration smoke test that runs the CLI command against a small DB fixture and verifies file created.

## Dev Notes

- Data source: canonical `prices` table in `dados/data.db` (SQLite). Path: `dados/data.db` relative to repo root.
- Output path: `snapshots/` folder in repo root. Ensure folder exists and is documented in README.
- Use `pandas` to export DataFrame to CSV (`df.to_csv(...)`) and `sqlalchemy` or existing DB layer for queries.
- Respect upsert semantics and canonical schema established in Epic 1 (see `docs/schema.json` for persisted columns: `ticker`, `date`, `open`, `high`, `low`, `close`, `volume`).
- Keep CSV header stable and documented; include canonical columns and optionally metadata header section in a separate `.meta` file if needed (see Story 2.2 for checksum/metadata details).
- CLI behavior: return non-zero exit code on errors; provide informative messages (rows found, rows exported, output path).
- Permissions: DB file `dados/data.db` should be owner-only by default; snapshots can be world-readable but document recommended perms.

### Implementation guidance (guardrails)

- Use existing DB abstraction (`db.read_prices`) if present; if not, implement a small helper that runs a parameterized SQL query with the canonical columns.
- Avoid loading entire DB into memory for large ranges; stream via `chunksize` in `pandas.read_sql_query` if dataset can be large.
- Ensure date parsing normalizes to UTC ISO8601 for filenames and metadata.
- Do not modify or delete data in `dados/data.db`.
- Add logging lines to record `job_id`, `ticker`, `started_at`, `finished_at`, `rows_fetched`, `status` to `ingest_logs` or `snapshots` metadata table as appropriate.

### Project Structure Notes

- Implement CLI command under `src/` (for example `src/cli/snapshots.py` or `src/pipeline/snapshot.py`) consistent with Typer entrypoints.
- Tests go under `tests/` following existing patterns; use `tests/fixtures` and `conftest.py` utilities for DB fixtures.

### References

- Source: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md#story-2.1-gerar-snapshot-csv-a-partir-de-dados-persistidos)
- DB: `dados/data.db` (SQLite)
- Output dir: `snapshots/`

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

### Completion Notes List

### File List

````

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/123
