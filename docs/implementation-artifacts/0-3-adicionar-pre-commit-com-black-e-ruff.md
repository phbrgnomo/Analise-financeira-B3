# Story 0.3: adicionar-pre-commit-com-black-e-ruff

Status: ready-for-dev

## Story

As a maintainer,
I want a pre-commit configuration with Black and Ruff,
so that code style is enforced and CI/linting are consistent across contributors.

## Acceptance Criteria

1. `.pre-commit-config.yaml` present with hooks for `black` and `ruff`.
2. README documents how to install and run pre-commit locally.
3. CI pipeline (placeholder) includes a job that runs pre-commit checks.

## Tasks

- [ ] Add `.pre-commit-config.yaml` with Black and Ruff hooks.
- [ ] Update README with install steps and usage.
- [ ] Add CI job placeholder (issue) to run pre-commit checks in CI.

## Dev Notes

- Use current stable versions compatible with Python 3.14.
- Tests: none required beyond running `pre-commit run --all-files` in CI locally.

### References
- PRD: quickstart and CI recommendations
- Sprint: docs/implementation-artifacts/sprint-status.yaml
