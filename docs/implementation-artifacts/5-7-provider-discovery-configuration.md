 # Story 5.7: provider-discovery-configuration

 Status: ready-for-dev

 ## Story

 As an Operator/Dev,
 I want a provider config YAML that enumerates available providers, priority and per-provider options,
 so that adding/removing providers is configuration-driven.

 ## Acceptance Criteria

 1. Given `config/providers.yaml`
    When the pipeline runs
    Then it reads provider priority, timeouts, API keys (via env) and selects providers according to policy (priority/fallback)
 2. A sample `config/providers.example.yaml` is included in the repo with documented fields and examples
 3. Provider selection supports priority and fallback policy; timeouts, max_retries and backoff settings are configurable per-provider
 4. API keys and secrets are read from environment variables (documented in `.env.example`) and NOT committed
 5. A `pydantic` model validates `config/providers.yaml` at startup and reports clear validation errors
 6. Contract tests / fixtures are provided under `tests/fixtures/providers/` and CI can run provider selection logic in `--no-network` mode

 ## Tasks / Subtasks

 - [ ] Create `config/providers.example.yaml` with fields: `name`, `priority`, `timeout_seconds`, `max_retries`, `backoff_factor`, `env_api_key`, `rate_limit_policy`
 - [ ] Implement loader `src/config/providers.py` exposing `load_providers(config_path)` returning validated list of provider configs (Pydantic)
 - [ ] Wire provider selection in ingest pipeline: pick provider by priority, fallback on failure according to policy
 - [ ] Add tests: `tests/config/test_providers_config.py` and fixtures in `tests/fixtures/providers/`
 - [ ] Document usage in `docs/planning-artifacts/epics.md` (Epic 5) and add short example in README quickstart

 ## Dev Notes

 - Config file path: `config/providers.yaml` (repo-level `config/` recommended)
 - Example: `config/providers.example.yaml` should be committed; real `config/providers.yaml` may be created by operator locally and contain no secrets
 - Use `pydantic.BaseModel` to define `ProviderConfig` with strict typing and defaults for `timeout_seconds=30`, `max_retries=3`, `backoff_factor=0.5`
 - Use env var names like `PROVIDER_<NAME>_API_KEY` and document in `.env.example`
 - Selection algorithm: order providers by `priority` ascending (1 = highest), iterate and attempt fetch with provider-specific settings; on failure, mark attempt in `ingest_logs` and continue to next provider until success or list exhausted
 - Respect provider `rate_limit_policy`; if provider returns 429 and `retry_after` header, honor it and log `provider_rate_limit=true` in `ingest_logs`
 - Keep provider-specific canonical mapping hooks in `src/adapters/mappings.py` and register provider id/name to mapping

 ### Project Structure Notes

 - New files:
   - config/providers.example.yaml
   - src/config/providers.py
   - tests/config/test_providers_config.py
   - tests/fixtures/providers/* (sample provider responses)
 - Integration points:
   - ingest pipeline (`src/main.py` / `pipeline.ingest`) should accept `--providers-config` optional arg
   - Adapter loader should accept provider config object for timeouts/retries

 ### References

 - Source: docs/planning-artifacts/epics.md#Epic-5 — Story 5.7 (provider discovery & configuration)

 ## Dev Agent Record

 ### Agent Model Used

 assistant

 ### Completion Notes List

 - Ultimate context analysis performed from `docs/planning-artifacts/epics.md` (Epic 5)
 - Created `docs/implementation-artifacts/5-7-provider-discovery-configuration.md` with acceptance criteria, tasks and dev notes

 ### File List

 - docs/implementation-artifacts/5-7-provider-discovery-configuration.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/148
