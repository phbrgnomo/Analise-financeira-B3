# Story 0.3: Adicionar pre-commit com black e ruff

Status: ready-for-dev

## Story

As a Maintainer,
I want `pre-commit` hooks configured for code style and linting,
so that commits enforce consistent formatting and basic lint rules.

## Acceptance Criteria

1. Given the repository with `.pre-commit-config.yaml`, when a contributor makes a commit, `pre-commit` runs `black` and `ruff` and prevents commit on failures.
2. Documentation in `README.md` explains how to install and run `pre-commit` locally.

## Tasks / Subtasks

- [ ] Add `pyproject.toml` dev-dependency note: `pre-commit`, `black`, `ruff` (or ensure present)
- [ ] Create `.pre-commit-config.yaml` configured to run `black` and `ruff` on relevant file types
  - [ ] Pin recommended versions or reference minimal compatible versions
  - [ ] Configure `ruff` with a project `pyproject.toml` section or `.ruff.toml` for rule set
- [ ] Add `pre-commit` install instructions to `README.md` (local setup and CI usage)
- [ ] Add a CI job step (GitHub Actions) to run `pre-commit` checks (`pre-commit run --all-files`) as part of `ci.yml` (suggested change only)
- [ ] Run `pre-commit run --all-files` locally to generate auto-format changes, commit them
- [ ] Add a small tests/verification step: `black --check .` and `ruff check .` in CI

## Dev Notes

- Files to create/modify:
  - `.pre-commit-config.yaml` (root)
  - `pyproject.toml` (dev-dependencies / tool settings)
  - optionally `.github/workflows/ci.yml` (add check step)
  - `README.md` (developer setup instructions)
  - optional `.ruff.toml` (if advanced `ruff` config needed)

- Recommended configuration (example):
  - `black` version: stable (recommend pin in dev-deps, e.g., `black==24.3.0` or latest compatible)
  - `ruff` version: stable (recommend pin, e.g., `ruff==0.10.0` or latest compatible)

- Example `.pre-commit-config.yaml` (implementation reference):

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.10.0
    hooks:
      - id: ruff
        args: ["--fix"]
```

- Example `pyproject.toml` snippets (tool config):

```toml
[tool.black]
line-length = 88

[tool.ruff]
line-length = 88
select = ["E", "F", "W", "C", "B", "I"]
ignore = ["E203", "W503"]
```

### Project Structure Notes

- Place `.pre-commit-config.yaml` at repo root so it applies to all contributors.
- Keep `pyproject.toml` tool sections consistent with `ruff` and `black` settings to avoid conflicts.

### Testing / Verification

- Local verification commands:
  - `pip install pre-commit` (or `poetry add --dev pre-commit black ruff`)
  - `pre-commit install`
  - `pre-commit run --all-files`
  - `black --check .` and `ruff check .`

- CI verification (recommended): include a step in `.github/workflows/ci.yml`:

```yaml
- name: Lint & Format Check
  run: |
    pip install pre-commit
    pre-commit run --all-files --show-diff-on-failure
    black --check .
    ruff check .
```

### References

- Source: docs/planning-artifacts/epics.md#story-03 (Epic 0 — Preparação do Ambiente de Desenvolvimento)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Story file created from template and epics source
- Acceptance criteria and tasks populated

### File List

- .pre-commit-config.yaml (to be added)
- pyproject.toml (may be updated)
- README.md (updated with instructions)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/21
