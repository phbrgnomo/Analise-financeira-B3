# Story 0.6: Criar .env.example e instruções de configuração local

Status: ready-for-dev

## Story

As a Developer,
I want a `.env.example` and clear instructions to set env vars locally,
so that I can configure API keys and local paths without committing secrets.

## Acceptance Criteria

1. Given the repository, when a developer copies `.env.example` to `.env` and fills placeholder values, then the project reads `.env` optionally (via `python-dotenv`) for local runs.
2. README explains which variables are required and which are optional.
3. `.env.example` contains at minimum: `YF_API_KEY=`, `DATA_DIR=./dados`, `SNAPSHOT_DIR=./snapshots`, `LOG_LEVEL=INFO` and brief comments.
4. Documentation includes a short snippet demonstrating using `python-dotenv` and a reminder to never commit real secrets.

## Tasks / Subtasks

- [ ] Create `.env.example` at repository root with placeholders and comments (AC 1,3)
  - [ ] Add recommended local defaults (`DATA_DIR`, `SNAPSHOT_DIR`, `LOG_LEVEL`) (AC 3)
- [ ] Add instructions section to `README.md` showing copying `.env.example` → `.env` and example usage via `poetry run main` (AC 2,4)
- [ ] Ensure codebase optionally loads `.env` using `python-dotenv` when present (dev note) (AC 1)
- [ ] Document security reminder and recommended `.gitignore` entry (AC 4)

## Dev Notes

- Preferred approach: use `python-dotenv` to load environment variables in local dev only; do NOT hardcode secrets in code or commit `.env`.
- Keep defaults sensible and non-secret (e.g., `DATA_DIR=./dados`).
- If the project later adopts a secrets manager for CI/CD, document the mapping from env vars to secrets there.
- Add a short code snippet to `src/main.py` or an initialization module demonstrating safe loading:

  - Load order suggestion: environment variables (OS) -> `.env` (optional) -> CLI flags

## Project Structure Notes

- Place `.env.example` at repository root. Add `.env` to `.gitignore` if not present.
- Document required env vars in `README.md` quickstart (docs/planning-artifacts/epics.md references Story 0.6).
- No new packages strictly required, but recommend adding `python-dotenv` to dev/runtime dependencies in `pyproject.toml` (optional dev-dep if only for local dev).

## References

- Source requirements: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md) (Story 0.6 section)
- Sprint tracking: [docs/implementation-artifacts/sprint-status.yaml](docs/implementation-artifacts/sprint-status.yaml)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Story file created with acceptance criteria, tasks, dev notes and references.

### File List

- `.env.example` (to be created by dev or automation task)
- `docs/implementation-artifacts/0-6-criar-env-example-e-instrucoes-de-configuracao-local.md`

```

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/109
