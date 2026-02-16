# Story 0.4: criar-skeleton-de-ci-github-workflows-ci-yml

Status: ready-for-dev

## Story

As a contributor,
I want a minimal GitHub Actions CI skeleton,
so that PRs run tests and basic checks automatically.

## Acceptance Criteria

1. `.github/workflows/ci.yml` exists with jobs: install deps, run pytest, (optional) markdown link check.
2. CI job exits non-zero on test failures.
3. README references CI and how to run locally.

## Tasks
- [ ] Add `.github/workflows/ci.yml` template (no secrets required).
- [ ] Document CI steps in README.
- [ ] Add issue for expanding CI (flake/ruff/black checks).

## Dev Notes
- Use `poetry install` and `poetry run pytest -q` in CI steps.
- Keep workflow minimal for MVP.
