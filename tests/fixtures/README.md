Fixtures for tests

- `sample_ticker.csv`: Small sample CSV for `PETR4.SA` used by unit and integration tests.

Usage

- Tests can load the CSV directly or use the provided `sample_db` fixture in `tests/conftest.py`.
- The fixture creates an in-memory SQLite DB and seeds the `prices` table with rows from `sample_ticker.csv`.

Location

- `tests/fixtures/sample_ticker.csv`
- `tests/conftest.py`

Notes

- Keep the sample CSV small (<100 rows) for fast CI.
- Do not include any secrets or provider API keys in fixtures.
