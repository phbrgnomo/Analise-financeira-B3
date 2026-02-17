# Story 0.5: adicionar-fixtures-de-teste-e-exemplo-de-dados-amostra

Status: ready-for-dev

## Story

As a Test Author,
I want example pytest fixtures and a small sample CSV for a ticker,
so that unit and integration tests can run deterministically and quickly.

## Acceptance Criteria

1. Given tests that rely on fixture data
   When pytest is executed
   Then tests use an in-repo sample CSV and SQLite in-memory fixtures and pass deterministically.
2. Sample CSV is small (< 100 rows), located at `tests/fixtures/sample_ticker.csv` and documented in `tests/fixtures/README.md`.
3. `tests/conftest.py` exposes a fixture that loads `tests/fixtures/sample_ticker.csv` into an in-memory SQLite database for tests.

## Tasks / Subtasks

- [ ] Add sample CSV: `tests/fixtures/sample_ticker.csv` (AC: #1, #2)
  - [ ] Ensure CSV has canonical columns: `ticker,date,open,high,low,close,adj_close,volume,source`
- [ ] Add `tests/fixtures/README.md` documenting the fixture and usage (AC: #2)
- [ ] Add `tests/conftest.py` with `sample_db` fixture to load CSV into in-memory SQLite (AC: #3)
- [ ] Add a simple example test that uses `sample_db` (optional follow-up task)

## Dev Notes

- Keep sample CSV tiny (5–20 rows) for fast CI and local runs.
- `conftest.py` uses stdlib `csv` + `sqlite3` to avoid heavy runtime deps in test surface.
- If project uses SQLAlchemy/pandas in tests, consider adding an adapter fixture to convert the in-memory DB to the expected interface.

### Project Structure Notes

- Fixtures located under `tests/fixtures` so CI and local runs include them by default.
- Prefer in-memory SQLite for isolation: `sqlite3.connect(':memory:')` used in fixture.
- If future stories add DB migration tooling, adopt the same fixture pattern to seed schema.

### References

- Source: docs/planning-artifacts/epics.md#Story-0.5

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

- Created `tests/fixtures/sample_ticker.csv`
- Created `tests/fixtures/README.md`
- Created `tests/conftest.py`
- Created story file at `docs/implementation-artifacts/0-5-adicionar-fixtures-de-teste-e-exemplo-de-dados-amostra.md`

### Completion Notes List

- Story file initialized from template and populated using epics entry for Story 0.5.
- Basic fixtures and documentation added to repository.

### File List

- tests/fixtures/sample_ticker.csv
- tests/fixtures/README.md
- tests/conftest.py


Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/23
