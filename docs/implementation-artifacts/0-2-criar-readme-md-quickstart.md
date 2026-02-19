# Story 0.2: Criar README.md Quickstart

Status: completed

## Story

As a New Contributor,
I want a concise README.md quickstart with required commands,
so that I can reproduce the quickstart experiment in ≤ 30 minutes.

## Acceptance Criteria

1. Given a developer on a fresh machine with Python 3.14 and Poetry
   - When they follow the README quickstart steps
   - Then they can run `poetry install` and `poetry run main --help` and execute a sample quickstart command
2. README lists example tickers and expected output locations (`snapshots/`, `dados/`).
3. README includes `.env` usage, required env vars and minimal troubleshooting notes.
4. README documents how to run the quickstart end-to-end: ingest → persist → snapshot → notebook (paths and expected outputs).

## Tasks / Subtasks

- [ ] Draft `README.md` quickstart content
  - [ ] Add prerequisites (Python, Poetry)
  - [ ] Add install steps (`poetry install`)
  - [ ] Add CLI examples (`poetry run main --help`, `poetry run main --ticker PETR4.SA --force-refresh`)
  - [ ] Add expected file locations and short explanation (`dados/`, `snapshots/`, `raw/`)
  - [ ] Add `.env.example` usage and required vars
  - [ ] Add troubleshooting and common errors
- [ ] Review against PRD and epics acceptance criteria
- [ ] Add links to other docs (playbooks, architecture, adapter-mappings)

## Dev Notes

- Quickstart goal: enable reproducible end-to-end run in ≤ 30 minutes (NFR-P1).
- Primary quickstart command: `poetry run main --ticker <TICKER> [--force-refresh]` (see FR16).
- Example tickers to include: PETR4.SA, VALE3.SA, ITUB4.SA.
- Ensure instructions reference `dados/data.db` location and `snapshots/` outputs.
- Mention using `python -m src.main` as alternative to `poetry run main` when Poetry not available.

### Project Structure Notes

- Entrypoint: `src/main.py` (CLI using Typer conventions).
- Data: `dados/` (SQLite `data.db`), `raw/` (raw CSVs per provider), `snapshots/` (generated CSV snapshots).
- Docs: `docs/planning-artifacts/` and `docs/implementation-artifacts/` for stories and artifacts.
- Tests: recommend `tests/` with fixtures in `tests/fixtures/`.

### Testing Quickstart Locally (minimal)

1. Install dependencies:

```bash
poetry install
```

2. Run help to confirm CLI:

```bash
poetry run main --help
# or
python -m src.main --help
```

3. Run quickstart example (mocked/provider may be required for CI-free run):

```bash
poetry run main --ticker PETR4.SA --force-refresh
```

Expected outcomes:
- `dados/data.db` created/updated with `prices` table
- `snapshots/<ticker>-<ts>.csv` generated with SHA256 checksum
- logs in `ingest_logs` or console indicating success

### References

- Source epics and acceptance criteria: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md)
- PRD: [docs/planning-artifacts/prd.md](docs/planning-artifacts/prd.md)
- Architecture: [docs/planning-artifacts/architecture.md](docs/planning-artifacts/architecture.md)
- Adapter mappings: [docs/planning-artifacts/adapter-mappings.md](docs/planning-artifacts/adapter-mappings.md)

## Dev Agent Record

### Agent Model Used
automation-agent

### Completion Notes List

- Created story file from template and epics PRD alignment.

### File List

- docs/implementation-artifacts/0-2-criar-readme-md-quickstart.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/105
