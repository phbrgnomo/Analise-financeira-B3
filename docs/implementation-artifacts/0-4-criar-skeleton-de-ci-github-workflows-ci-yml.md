# Story 0.4: criar-skeleton-de-ci-github-workflows-ci-yml

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a CI Engineer,
I want a GitHub Actions workflow that runs install + tests + lint,
so that pull requests verify project health automatically.

## Acceptance Criteria

1. Given a push or PR to any branch, the `ci.yml` runs a lightweight CI matrix (Python 3.14) with steps:
   - `poetry install --no-dev` (install runtime deps for quick smoke)
   - `poetry install` (install dev deps)
   - `poetry run pytest -q --maxfail=1`
   - `ruff . --select` and `black --check .`
2. The workflow reports pass/fail in the PR status and exposes logs/artifacts for failed runs.
3. CI uses mocked providers for any network-dependent integration tests (no real network calls in CI by default).
4. Artifacts (test results, coverage, generated snapshots for failed runs) are uploaded for debugging when jobs fail.

## Tasks / Subtasks

- [ ] Create `.github/workflows/ci.yml` with jobs:
  - [ ] `lint` job: run `ruff` and `black --check` on codebase
  - [ ] `test` job: install deps and run `pytest -q --maxfail=1`
  - [ ] `smoke` job: `poetry install --no-dev` + quick smoke tests
  - [ ] Matrix for Python 3.14 (single axis) and OS `ubuntu-latest`
  - [ ] Upload artifacts on failure (pytest junit, logs, snapshots)
  - [ ] Use cache for Poetry/venv to speed up CI where applicable
  - [ ] Ensure secrets are referenced only via GitHub Secrets and `.env` is not committed
- [ ] Add `tests/ci` helper steps to run mocked integration (fixtures) and produce deterministic snapshot
- [ ] Document CI run steps and expected outputs in README (quick reference section)
- [ ] Add `ci.yml` job badges to `README.md` (optional)

## Dev Notes

- Use `poetry` for dependency management in CI. Follow `architecture.md` recommendation for starter stack (Poetry + Typer + pandas + SQLAlchemy + pytest).
- Mock external providers in CI (use `tests/fixtures` and `pytest` markers) to avoid network flakiness and rate limits.
- Keep CI matrix minimal to reduce runtime and cost — prefer a single Python version (3.14) for now.
- Upload artifacts (JUnit, pytest logs, sample snapshot CSV + .checksum) on failure to assist debugging.
- Do not commit secrets; access via GitHub Actions `secrets.*`.

### Project Structure Notes

- Workflow path: `.github/workflows/ci.yml` (must be exact for GitHub Actions)
- CI should run relative to repository root and use `poetry` commands as in PRD/architecture.
- Ensure `pyproject.toml` exists and contains required dependencies (runtime + dev) before enabling full CI.

### References

- Source: docs/planning-artifacts/epics.md (Story 0.4)
- Architecture guidance: docs/planning-artifacts/architecture.md
- PRD quickstart & CI requirements: docs/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created

### File List

- .github/workflows/ci.yml (to be created by implementer)

```
