# Story 0.5: adicionar-fixtures-de-teste-e-exemplo-de-dados-amostra

Status: ready-for-dev

## Story

As a QA/Dev,
I want fixtures and sample data for tests,
so that unit and integration tests can run deterministically in CI.

## Acceptance Criteria

1. `tests/fixtures/` contains a sample CSV and pytest fixture for an in-memory SQLite DB.
2. Example snapshot CSV included in `docs/samples/` with expected header and metadata.
3. README documents how to use fixtures in local testing.

## Tasks
- [ ] Add pytest fixtures for SQLite temporary DB.
- [ ] Add sample CSV(s) in `docs/samples/`.
- [ ] Document usage in README/tests section.

## Dev Notes
- Keep sample files small (1-10 rows) for fast CI.
- Provide simple helper to load sample CSV into DB for integration smoke tests.
