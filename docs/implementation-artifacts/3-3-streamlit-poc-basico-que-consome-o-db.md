---
generated: 2026-02-17T00:00:00Z
story_key: 3-3-streamlit-poc-basico-que-consome-o-db
epic: 3
story_num: 3
status: ready-for-dev
owner: Phbr
---

# Story 3.3: streamlit-poc-basico-que-consome-o-db

Status: ready-for-dev

## Story

As a User,
I want a minimal Streamlit POC that reads prices and returns from the local SQLite database (`dados/data.db`) for a selected ticker and date range,
so that I can quickly inspect price and return series and validate end‑to‑end ingestion + persistence flows.

## Acceptance Criteria

1. The POC is runnable locally with a single command (example): `streamlit run src/apps/streamlit_poc.py` or via the CLI quickstart wrapper `poetry run main --streamlit`.
2. UI inputs: selectable `ticker` (autocomplete from DB or provided list), `start_date`, `end_date`, and a `refresh`/`force-refresh` toggle for reloading data if needed.
3. Data source: reads from `dados/data.db` through the project's DB layer (use `db.read_prices(ticker, start, end)` contract). No direct raw file parsing in the app.
4. Displays at minimum:
   - Time series chart for `close` / `adj_close` prices
   - Time series chart for daily returns (simple pct change) with selectable annualization note
   - Summary statistics: rows loaded, date range, checksum of the underlying snapshot (if applicable)
5. The app handles empty results gracefully (user-friendly message and suggested next steps).
6. Developer-run instructions are included in the file (how to run locally, env vars, and required packages).
7. The POC code location: `src/apps/streamlit_poc.py` and minimal helper functions in `src/db` or `src/utils` as needed.
8. Basic smoke test: importing the app module and calling the main data-loading function must succeed against the sample fixture DB or `dados/data.db`.

## Tasks / Subtasks

- [ ] Create `src/apps/streamlit_poc.py` with Streamlit UI and data-loading helpers (AC 1-4)
  - [ ] Implement `load_prices(ticker, start, end)` using `src/db/db.py` contract
  - [ ] Implement plotting (plotly or altair) with fallbacks to matplotlib if missing
- [ ] Add docs section in `docs/playbooks/quickstart-ticker.md` showing how to run the POC (AC 6)
- [ ] Add a lightweight smoke test in `tests/test_streamlit_poc.py` that validates data-loading function (AC 8)

## Dev Notes

- Architecture constraints: This is a local single‑user POC; prefer read-only DB access patterns and avoid introducing concurrent writers from the UI. See `docs/planning-artifacts/architecture.md` for rationale and constraints (SQLite single-user tradeoffs).
- Use existing DB contract `db.read_prices(ticker, start, end)` (see `docs/planning-artifacts/epics.md` and `architecture.md`). Do not bypass the `src/db` layer.
- Keep dependencies minimal: Streamlit (pinned at a sensible stable version), `pandas` for ETL, `plotly` or `altair` for interactive charts. Prefer whichever is already in `pyproject.toml` otherwise add to runtime deps.
- Testing: create a smoke test that uses `tests/fixtures/sample_ticker.csv` loaded into a temporary SQLite DB via `tests/conftest.py`.

### Project Structure Notes

- Recommended file: `src/apps/streamlit_poc.py`
- DB helper: `src/db/db.py` (expose `read_prices`) — reuse existing patterns
- Tests: `tests/test_streamlit_poc.py` (use fixtures/sample_ticker.csv)

### References

- Source: docs/planning-artifacts/epics.md (FR19, FR20, FR22)
- Architecture constraints and guidance: docs/planning-artifacts/architecture.md
- Sprint status entry: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Ultimate context engine analysis completed; file created from template and project artifacts.

### File List

- src/apps/streamlit_poc.py (suggested)
- src/db/db.py (use existing contract)
- tests/test_streamlit_poc.py (suggested smoke test)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
