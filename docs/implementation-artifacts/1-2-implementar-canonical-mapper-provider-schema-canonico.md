# Story 1.2: Implementar Canonical Mapper (Provider -> Schema canônico)

Status: review

## Story

As a Developer,
I want a canonical mapper that normalizes provider DataFrames to the project's canonical schema,
so that downstream modules can rely on a consistent format for persistence and processing.

## Acceptance Criteria

1. Given a raw `DataFrame` from a provider adapter (e.g., `yfinance`), when the canonical mapper is executed, then it returns a `DataFrame` with canonical columns: `ticker`, `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`, `source`, `fetched_at`.
2. The mapper computes `raw_checksum` (SHA256) for the raw payload and includes it in metadata persisted alongside canonical rows.
3. `fetched_at` is normalized to UTC ISO8601 and time zone handling is documented.
4. The mapper provides a lightweight `pandera` schema used to validate canonical `DataFrame` in unit tests and CI.
5. Mapper has clear error handling and returns descriptive errors when required columns are missing or types are invalid.

## Tasks / Subtasks

- [x] Implement `src/etl/mapper.py` with `to_canonical(df, provider_name, ticker)` returning canonical `DataFrame`.
  - [x] Compute and attach `raw_checksum` (SHA256) for the raw payload; persist or return as metadata.
  - [x] Normalize `fetched_at` to UTC ISO8601 in `metadata` column(s).
  - [x] Implement `pandera` `DataFrameSchema` for canonical schema and integrate validation call.
- [x] Add unit tests `tests/test_mapper.py` covering:
  - [x] Successful mapping from `yfinance`-like input to canonical schema.
  - [x] Handling of missing columns (fail with clear error code/message).
  - [x] `raw_checksum` correctness for example payloads.
- [x] Document mapping examples in `docs/planning-artifacts/adapter-mappings.md` (yfinance → canonical example).
- [x] Add integration smoke test (mock provider) to verify canonical output shape used by DB layer.
- [x] Documentar o que foi implantado nessa etapa em `docs/sprint-reports` conforme definido no FR28 (`docs/planning-artifacts/prd.md`)

## Dev Notes

- Technical stack: follow project architecture conventions (see docs/planning-artifacts/architecture.md). Use `pandas` for transformations, `pandera` for DataFrame validation, `pydantic` for config objects if needed, and `python-dotenv` for env.
- Persisting raw checksum and canonical rows: mapper should return canonical `DataFrame` plus metadata required by `src/db/db.py` (upsert by `(ticker, date)`).
- Error handling: raise typed exceptions (e.g., `MappingError`) with structured message to be consumed by `pipeline.ingest`.
- Timezones: normalize all datetimes to UTC with timezone-aware ISO8601 (e.g., `2026-02-17T12:34:56Z`). Document decisions in the mapper docstring.
- File permissions: follow architecture guidance for file writes; raw files and DB should document recommended permissions (owner-only for DB). See architecture.md.

### Project Structure Notes

- `src/etl/mapper.py` — canonical mapper implementation and `pandera` schema.
- `src/adapters/` — provider adapters supply raw `DataFrame` and `source` metadata (e.g., `yfinance_adapter.py`).
- `src/db/db.py` — DB helpers that expect canonical `DataFrame` shape for upsert.
- `docs/planning-artifacts/adapter-mappings.md` — add mapping examples for `yfinance`.

### References

- Source: docs/planning-artifacts/epics.md#story-1.2
- Architecture: docs/planning-artifacts/architecture.md
- Adapter mappings: docs/planning-artifacts/adapter-mappings.md

## Dev Agent Record

### Agent Model Used

GPT-5 mini (implementação original)
GPT-4.5-Turbo (validação e conclusão - 2026-02-20)

### Implementation Notes

**Implementação já completa e testada (2026-02-20)**

A story 1-2 foi encontrada com implementação completa:
- `src/etl/mapper.py`: função `to_canonical()` com validação pandera, checksum SHA256, e normalização de timezone UTC
- `tests/test_mapper.py`: 8 testes unitários cobrindo todos os cenários (sucesso, erros, validação)
- `tests/integration/test_mapper_integration.py`: 2 testes de integração validando compatibilidade com DB layer
- `docs/planning-artifacts/adapter-mappings.md`: documentação completa com exemplos

**Ações executadas nesta sessão:**
1. Validação de todos os testes: 53 passed ✅
2. Execução de pre-commit para garantir conformidade de código ✅
3. Execução de CI orchestrator (lint, tests, smoke, integration) ✅
4. Criação de sprint report em `docs/sprint-reports/1-2-implementacao-canonical-mapper.md` ✅
5. Atualização da story para status "review" ✅

**Decisões técnicas validadas:**
- Uso de `pandera` para validação de schema DataFrame
- Checksum SHA256 calculado sobre CSV representation (determinístico e reproduzível)
- Metadata armazenada em `DataFrame.attrs` (raw_checksum, provider, ticker)
- Timezone normalizado para UTC ISO8601 com formato `YYYY-MM-DDTHH:MM:SSZ`
- Exception `MappingError` para todos os casos de erro de mapeamento

### Debug Log References

- All tests passing: 53 passed, 11 warnings
- CI orchestrator: all 4 stages passed (lint, unit tests, smoke, integration)
- Pre-commit hooks: ruff, fix-end-of-files, trailing-whitespace all passed

### Completion Notes List

✅ **Story 1.2 totalmente implementada e validada**

**Implementação:**
- Canonical mapper com todas as features especificadas
- Validação pandera integrada
- Checksum SHA256 para auditoria
- Timezone-aware UTC timestamps

**Testes:**
- 8 testes unitários (100% dos cenários cobertos)
- 2 testes de integração (smoke tests para DB layer)
- Todos os testes passando sem regressões

**Documentação:**
- Exemplo completo de mapping yfinance → canonical
- Código de exemplo integrado
- Sprint report detalhado criado

**Qualidade:**
- Pre-commit hooks passando (ruff, trailing whitespace, end-of-files)
- CI orchestrator passando em todas as etapas
- Código em conformidade com project-context.md (line-length 88, Python ^3.12)

### File List

- src/etl/mapper.py (implementação do canonical mapper)
- tests/test_mapper.py (8 testes unitários)
- tests/integration/test_mapper_integration.py (2 testes de integração)
- docs/planning-artifacts/adapter-mappings.md (documentação de exemplos)
- docs/sprint-reports/1-2-implementacao-canonical-mapper.md (sprint report - novo)
- docs/implementation-artifacts/1-2-implementar-canonical-mapper-provider-schema-canonico.md (atualizado)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/115
