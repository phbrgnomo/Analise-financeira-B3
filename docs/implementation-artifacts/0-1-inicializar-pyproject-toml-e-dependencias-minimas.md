# Story 0.1: Inicializar pyproject.toml e dependências mínimas

Status: ready-for-dev

## Story

As a Developer,
I want a minimal `pyproject.toml` with declared dependencies and dev-dependencies,
so that I can install and run the project and tests consistently using `poetry`.

## Acceptance Criteria

1. Given a clean checkout of the repository, when I run `poetry install` (or `poetry install --no-dev` for CI) then the runtime and dev dependencies are installed without errors.
2. `poetry run main --help` (or `python -m src.main --help`) shows the CLI help output.
3. `pyproject.toml` contains pinned/minimal versions for key packages (e.g., `pandas`, `sqlalchemy`, `typer`, `pytest`) and documents any important constraints.

## Tasks / Subtasks

- [ ] Add `pyproject.toml` with runtime dependencies: `pandas`, `sqlalchemy`, `typer`, `python-dotenv`.
- [ ] Add dev-dependencies: `pytest`, `black`, `ruff`, `pre-commit` and configure basic pre-commit hooks.
- [ ] Add entrypoint script `main` in `src/main.py` and verify `poetry run main --help`.
- [ ] Document quickstart commands in README.md (install, run, test).

## Dev Notes

- Keep versions conservative and explicitly pinned for reproducibility in early phases.
- Follow existing project layout as decribed in `docs/architecture.md` in the ## Project Structure & Boundaries section
- Ensure compatibility with Python 3.14 as noted in planning artifacts.

### Project Structure Notes

- Place `pyproject.toml` at repository root.
- Add `tests/` skeleton and `tests/fixtures/` for sample CSVs (see `docs/planning-artifacts/epics.md`).

### References

- Source: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md)
- Architecture: [docs/planning-artifacs/architecture.md](docs/planning-artifacts/epics.md)
- Sprint status: [docs/implementation-artifacts/sprint-status.yaml](docs/implementation-artifacts/sprint-status.yaml)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Ultimate context engine analysis completed for story foundation.

### File List

- `pyproject.toml` (create)
- `src/main.py` (verify entrypoint)
- `README.md` (update quickstart)
- `tests/` (skeleton and fixtures)


Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/104
