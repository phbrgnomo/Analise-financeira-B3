---
story_id: 5.5
story_key: 5-5-provider-contract-tests-harness-integration-tests
epic: 5
status: ready-for-dev
created_by: BMAD automated run
created_at: 2026-02-17T00:00:00Z
---

# Story 5.5: Provider contract tests & harness (integration tests)

Status: ready-for-dev

## Story

As a QA/Dev,
I want a test harness and contract tests for adapters,
so that providers conform to expected schema and behavior (retries, error codes, timezones).

## Acceptance Criteria

1. Given an adapter implementation
   When contract tests run (CI or locally)
   Then they validate: returned columns, presence of `source` and `fetched_at`, proper retries, and deterministic behavior under `--no-network` fixtures.

2. Contract tests are runnable via `pytest tests/adapters/test_contract.py` and include a `--provider alpha|yfinance --use-fixture` mode.

3. Tests validate retries/backoff behavior, recorded `raw_checksum`, and consistent timezone handling for `fetched_at`.

4. Contract tests are runnable in CI using `--no-network` and fixtures under `tests/fixtures/providers/`.

## Tasks / Subtasks

- [ ] Criar `tests/adapters/test_contract.py` com modos: `--provider <name>` e `--use-fixture`.
- [ ] Adicionar fixtures de resposta em `tests/fixtures/providers/<provider>/` com exemplos de raw responses e CSVs.
- [ ] Implementar fixture runner que popula o adapter com `--no-network` mode.
- [ ] Documentar execução em `docs/planning-artifacts/adapter-mappings.md` e README de testes.
- [ ] Integrar job no CI (ex.: `ci/contract-tests.yml`) que roda contract tests com fixtures e falha em regressões.

## Dev Notes

- Fonte de requisitos: `docs/planning-artifacts/epics.md#Story-5.5` (Epic 5 — Adaptadores & Normalização).
- Testes devem validar colunas canônicas, presença de metadados (`source`, `fetched_at`, `raw_checksum`) e comportamento determinístico com `--no-network`.
- Contract tests devem oferecer modos de execução local e em CI; CI roda com fixtures para garantir estabilidade.
- Logs de tentativa de ingest devem incluir `job_id`, `provider`, `attempt`, `status_code`, `retry_after`.

### Guidelines rápidas para implementação

- Use `pytest` + fixtures; considere `responses` ou `requests-mock` para simular endpoints quando necessário.
- Estruture testes para reutilizar casos entre provedores (test matrix: columns, metadados, retries/backoff, timezone normalization).
- Forneça utilitário `tests/adapters/fixtures_loader.py` que carrega fixtures e expõe modo `--use-fixture` para o adapter.

### Project Structure Notes

- Tests: `tests/adapters/test_contract.py`
- Fixtures: `tests/fixtures/providers/<provider>/` (raw json/csv + expected canonical csv)
- Docs: atualizar `docs/planning-artifacts/adapter-mappings.md` e `docs/implementation-artifacts/5-5-provider-contract-tests-harness-integration-tests.md`

### References

- Source: docs/planning-artifacts/epics.md#Story-5.5
- Architecture guidance: docs/planning-artifacts/architecture.md (adapter → canonical mapper pattern)

## Developer Context & Guardrails

- Arquitetura: seguir a camada `Adapter -> Canonical Mapper -> DB` definida em `architecture.md`.
- Test strategy: contract tests devem rodar sem rede (`--no-network`) em CI; use fixtures em `tests/fixtures/providers/`.
- Não alterar contratos `Adapter.fetch(ticker) -> pd.DataFrame` nem o campo metadado mínimo `source`, `fetched_at`, `raw_checksum` sem versão (versionar mudanças via `Adapter.vX`).

## Technical Requirements

- `pytest` como runner de testes; não introduzir frameworks pesados adicionais.
- Fornecer flag/mode `--use-fixture` ou env `USE_FIXTURES=true` para executar tests contra fixtures locais.
- Expor `tests/adapters/conftest.py` com fixtures reutilizáveis e utilitários de carregamento.

## Architecture Compliance

- Validar que os tests não dependam de chamadas reais a provedores em CI (usar fixtures). Se houver chamadas reais, devem estar marcadas e opcionais.
- Garantir que timezone em `fetched_at` seja UTC normalizado e testado.

## Library / Framework Requirements

- `pytest` (dev-dependency)
- `requests-mock` ou `responses` para mocking HTTP
- `pandas` para manipulação de DataFrames em fixtures/validações

## File structure requirements

- Criar `tests/adapters/test_contract.py` e `tests/fixtures/providers/` com subpastas por provider.

## Testing Requirements

- Cobrir: schema de colunas, metadados, retries/backoff, timezone normalization, checksum determinismo.
- Test runner: `pytest tests/adapters/test_contract.py --provider yfinance --use-fixture`

## Previous Story Intelligence

- Não foram encontrados arquivos de implementação anteriores para Epic 5 em `docs/implementation-artifacts/`.

## Git Intelligence

- Repositório atual mostra implementação de base (epics, PRD, arquitetura) mas sem histórias implementadas para Epic 5; siga os padrões de nomes e localização usados em outras stories (ex.: `docs/implementation-artifacts/0-...` arquivos).

## Latest Technical Information

- Arquitetura recomenda `pandas`, `SQLAlchemy` e `pytest` para execução local; seguir recomendações de `architecture.md` para decisões de biblioteca.

## Project Context Reference

- PRD: docs/planning-artifacts/prd.md
- Epics: docs/planning-artifacts/epics.md#Story-5.5

## Story Completion Status

- Status setado para `ready-for-dev`.

---

Completion Note: Ultimate context engine analysis completed - comprehensive developer guide created

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/
