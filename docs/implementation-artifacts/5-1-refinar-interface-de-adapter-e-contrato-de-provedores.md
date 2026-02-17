---
generated: 2026-02-17T00:00:00Z
from_workflow: _bmad/bmm/workflows/4-implementation/create-story
story_key: 5-1-refinar-interface-de-adapter-e-contrato-de-provedores
epic: 5
story_id: 5.1
status: ready-for-dev
owner: Phbr
---

# Story 5.1: Refinar interface de Adapter e contrato de provedores

Status: ready-for-dev

## Story

As a Developer,
I want a stable, versioned Adapter interface and contract for providers,
so that new provider implementations can be added without changing core logic.

## Acceptance Criteria

1. Given the Adapter interface exists
   When a new provider is implemented
   Then it conforms to `Adapter.fetch(ticker) -> pd.DataFrame` with documented metadata fields (`source`, `fetched_at`, `raw_checksum`) and error codes.
2. The interface is versioned (e.g., `Adapter.v1`) with a changelog entry in `docs/planning-artifacts/adapter-mappings.md`.
3. Adapters must support `--no-network` fixtures for CI/contract tests and expose retry/backoff behavior controlled by config/env (e.g., `ADAPTER_MAX_RETRIES`).

## Tasks / Subtasks

- [ ] Definir e declarar `Adapter` interface (`src/adapters/interface.py`) with type hints and docstrings
  - [ ] Version the interface (`Adapter.v1`) and add changelog entry in `docs/planning-artifacts/adapter-mappings.md`
- [ ] Implement adapter contract examples and a small shim for `yfinance` + `alphavantage` (samples or fixtures)
- [ ] Add `--no-network` / fixture mode to adapters and a test fixture under `tests/fixtures/providers/`
- [ ] Create contract tests `tests/adapters/test_contract.py` (pytest) with `--provider` and `--use-fixture` modes
- [ ] Document provider config sample in `config/providers.example.yaml` and loader using `pydantic` in `src/config/providers.py`
- [ ] Update README/dev playbook with how to add provider and run contract tests

## Dev Notes

- Technical constraints: follow existing project stack (Python, `pandas`, `sqlalchemy`, `typer`). See `docs/planning-artifacts/epics.md` (Epic 5) for context.
- Interface must return canonical-compatible DataFrame (columns: `ticker`, `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`, `source`, `fetched_at`) or raw provider DataFrame alongside metadata.
- Metadata contract: include `source` (str), `fetched_at` (UTC ISO8601), `raw_checksum` (SHA256 hex), and a machine-readable `error_code` when failing.
- Retry behaviour: honor provider `Retry-After` headers when present; apply exponential backoff with jitter; log attempts to `ingest_logs` with fields (`provider`, `attempt`, `status_code`, `retry_after`, `job_id`).

### Project Structure Notes

- Suggested new files/paths:
  - `src/adapters/interface.py`  — Adapter interface & types
  - `src/adapters/yfinance_adapter.py` — example shim (if not already present)
  - `src/adapters/alphavantage_adapter.py` — example adapter (story 5.2)
  - `src/config/providers.py` — provider loader (pydantic)
  - `config/providers.example.yaml` — sample configuration
  - `tests/adapters/test_contract.py` — contract tests using `tests/fixtures/providers/`

### Testing Requirements

- Add contract tests that run in CI with `--no-network` (use fixtures). Ensure tests validate: returned columns, presence of `source` and `fetched_at`, retry semantics, and `raw_checksum` generation.
- Ensure unit tests exist for interface versioning and changelog presence (validate `docs/planning-artifacts/adapter-mappings.md` contains mapped entry).

### References

- Epic context and requirements: `docs/planning-artifacts/epics.md` (Epic 5 — Adaptadores & Normalização)
- Adapter mappings doc (to update): `docs/planning-artifacts/adapter-mappings.md`
- Sprint tracking: `docs/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Story file created from template and marked `ready-for-dev` in `docs/implementation-artifacts/sprint-status.yaml`.

### File List

- docs/implementation-artifacts/5-1-refinar-interface-de-adapter-e-contrato-de-provedores.md
