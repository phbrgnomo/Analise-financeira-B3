# Story 0.4: criar-skeleton-de-ci-github-workflows-ci-yml

Status: in-progress

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
  - [x] `lint` job: run `ruff` and `black --check` on codebase
  - [x] `test` job: install deps and run `pytest -q --maxfail=1`
  - [x] `smoke` job: `poetry install --no-dev` + quick smoke tests
  - [x] Matrix for Python 3.14 (single axis) and OS `ubuntu-latest`
  - [x] Upload artifacts on failure (pytest junit, logs, snapshots)
  - [x] Use cache for Poetry/venv to speed up CI where applicable
  - [x] Ensure secrets are referenced only via GitHub Secrets and `.env` is not committed
  - [x] Add `tests/ci` helper steps to run mocked integration (fixtures) and produce deterministic snapshot
  - [x] Document CI run steps and expected outputs in README (quick reference section)
  - [x] Add `ci.yml` job badges to `README.md` (optional)
  - [x] Documentar o que foi implantado nessa etapa conforme o FR28 (`docs/planning-artifacts/prd.md`)

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

- Implementação inicial do CI aplicada: jobs `lint`, `test`, `smoke`; cache de Poetry; upload de artifacts em falhas; matrix Python 3.14.

- Documentado em `docs/sprint-reports/epic0-story0-4-ci-implementation.md` (reproduzível, comandos e paths de snapshot)

### File List

- .github/workflows/ci.yml (created/modified)
- tests/ci/smoke.sh (created)
- tests/ci/README.md (created)
- README.md (modified - CI Quick Reference added)
- docs/implementation-artifacts/sprint-status.yaml (modified - story marked in-progress)

### Next Steps Suggested

- Add CI badges to `README.md` (optional).
- Implement `tests/ci` fixtures and mocked integration helpers to ensure deterministic CI runs.
- Update story `Status:` to `in-progress` (if you want file-level sync) — currently left as `ready-for-dev` per your request.
- Open PR for these changes and run CI in GitHub to validate workflow behavior in runner environment.

### File List

- .github/workflows/ci.yml (to be created by implementer)

## Review Follow-ups (AI)

- [x] [AI-Review][HIGH] Ajustar gatilhos do CI para rodar em qualquer branch (`push` / `pull_request`) — aplicado (`.github/workflows/ci.yml`).
- [x] [AI-Review][HIGH] Adicionar verificação/guard no `smoke` job para garantir que `tests/ci/smoke.sh` exista antes de executar — aplicado (`.github/workflows/ci.yml`).
- [x] [AI-Review][MEDIUM] Adicionar helpers e testes determinísticos em `tests/ci/` (fixtures, `conftest.py`, `test_mock_provider.py`) — aplicado (`tests/ci/*`).
- [x] [AI-Review][HIGH] Sincronizar status da story com `sprint-status.yaml` — aplicado (story `Status:` atualizado para `in-progress`).
- [ ] [AI-Review][HIGH] Remover snapshots gerados do repositório e mover para artifacts do CI (não commitar CSV/.checksum). Current: `snapshots_test/PETR4_snapshot.csv` está versionado — ação pendente.
- [ ] [AI-Review][MEDIUM] Revisar e hardenizar testes CI adicionais para garantir isolamento e evitar dependências de ambiente (mais cobertura de edge-cases).
- [ ] [AI-Review][MEDIUM] Adicionar caching/otimizações ao `lint` job se necessário (ex.: cache para dependências do linter) — sugerido.
- [ ] [AI-Review][LOW] Opcional: adicionar `fetch-depth: 0` ao `actions/checkout` se histórico for necessário.
- [ ] [AI-Review][LOW] Verificar e atualizar badge do CI no `README.md` conforme branch padrão.

### Review Actions Taken

- Files changed and committed in this review:
  - `.github/workflows/ci.yml`
  - `tests/ci/smoke.sh`
  - `tests/ci/conftest.py`
  - `tests/ci/test_mock_provider.py`
  - `tests/ci/README.md`
  - `docs/sprint-reports/epic0-story0-4-ci-implementation.md`
  - `docs/implementation-artifacts/0-4-criar-skeleton-de-ci-github-workflows-ci-yml.md` (this file updated)

If you want, I can now:

1. Remove `snapshots_test/*` from the repo and add a CI-only upload flow (recommended).
2. Create subtasks in the story for remaining unchecked items.
3. Open a Pull Request with these changes.


Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/107
