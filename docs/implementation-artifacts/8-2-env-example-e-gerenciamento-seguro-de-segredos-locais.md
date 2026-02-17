---
generated: 2026-02-17T00:00:00Z
story_key: 8-2-env-example-e-gerenciamento-seguro-de-segredos-locais
story_id: 8.2
status: ready-for-dev
---

# Story 8.2: .env.example e gerenciamento seguro de segredos locais

Status: ready-for-dev

## Story

As a Developer,
I want a clear `.env.example` and guidance for secret handling,
so that contributors do not commit secrets and can run locally using `python-dotenv` safely.

## Acceptance Criteria

1. A `.env.example` file exists at repository root listing required and optional variables with placeholder values.
2. README documents which variables are required vs optional and includes a short snippet showing `python-dotenv` usage or how `main` reads env.
3. The README warns contributors to never commit real `.env` files and suggests adding `.env` to `.gitignore`.
4. A pre-commit hook is suggested/installed (or documented) to detect secrets (e.g., `detect-secrets`) and guidance is provided to fail commits when secrets are present.
5. A short runbook entry (docs/operations/runbook.md or docs/implementation-artifacts/runbook-secrets.md) points to remediation steps and secret rotation guidance.

## Tasks / Subtasks

- [ ] Add `.env.example` to repository root with required vars and comments
- [ ] Update `README.md` with env setup instructions and secret handling guidance
- [ ] Add/enable pre-commit detection guidance for secrets (recommend `detect-secrets` and link to setup)
- [ ] Add a short runbook snippet for secret rotation and incident handling (one paragraph)
- [ ] Add verification command example: `poetry run main security verify-secrets` (documented; optional helper script)

## Dev Notes

- Required env variables (suggested in `.env.example`):
  - YF_API_KEY=        # optional: provider-specific
  - DATA_DIR=./dados
  - SNAPSHOT_DIR=./snapshots
  - LOG_LEVEL=INFO
- `python-dotenv` is the recommended local loader; code should fall back to environment variables when `.env` is absent.
- Do NOT commit real secrets. Recommend adding `.env` to `.gitignore` and using a secret manager for production deployments.
- Prefer minimal scope: local dev only uses `.env`. Production should use environment or secret manager (Vault, AWS Secrets Manager, etc.).

### Security Guidance (must-follow)

- Documented guidance must mention: never store long-lived production secrets in repo; rotate any leaked secrets immediately; follow incident runbook.
- Recommend pre-commit plugin: `detect-secrets` with baseline checked into repo and CI verification step in future (Story 8.4/8.3).

### Project Structure Notes

- Place `.env.example` at repository root alongside `pyproject.toml` and `README.md`.
- If adding helper scripts, put them under `scripts/` or `bin/` with executable bit and documentation in README.

### Testing / Verification

- Manual verification steps in README:
  1. Copy `.env.example` → `.env` and fill placeholders.
  2. Run `poetry run main --help` to confirm CLI reads env when applicable.
  3. (Optional) Run `detect-secrets --scan` locally to validate no secrets are accidentally present.

### References

- Source: docs/planning-artifacts/epics.md (Epic 8 — Segurança Operacional)
- Security checklist: docs/implementation-artifacts/sprint-status.yaml (development tracking)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Ultimate context analysis completed for Story 8.2

### File List

- .env.example (to be created)
- README.md (updated section)
- .gitignore (ensure `.env` present)
- docs/implementation-artifacts/8-2-env-example-e-gerenciamento-seguro-de-segredos-locais.md (this file)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
