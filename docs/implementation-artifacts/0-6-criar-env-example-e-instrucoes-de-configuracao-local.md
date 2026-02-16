# Story 0.6: criar-env-example-e-instrucoes-de-configuracao-local

Status: ready-for-dev

## Story

As a developer,
I want a `.env.example` and setup instructions,
so that contributors can configure API keys and local settings safely.

## Acceptance Criteria

1. `.env.example` present with placeholders for provider keys and common vars.
2. README documents how to populate `.env` and use `python-dotenv` in development.
3. Local setup steps (venv/poetry, install) documented.

## Tasks
- [ ] Create `.env.example` at project root.
- [ ] Document local configuration and secrets handling in README.
- [ ] Add note about not committing secrets and recommend `.gitignore` entries.

## Dev Notes
- Keep example minimal and safe (no real keys).
- Recommend usage of `.env` only for development; CI uses secrets store.
