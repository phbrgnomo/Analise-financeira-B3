---
title: "1.10 - Cache de Snapshots e Ingestão Incremental"
status: completed
story_key: 1-10-cache-de-snapshots-e-ingestao-incremental
epic: 1
story_num: 10
generated: 2026-02-17T15:40:00Z
---

# Story 1.10: cache-de-snapshots-e-ingestao-incremental

Status: completed

## Story

Como engenheiro de dados,
quero implementar um mecanismo de cache para snapshots e um fluxo de ingestão incremental,
para que o processo de ingestão seja mais rápido, idempotente e evite reprocessamento desnecessário.

## Acceptance Criteria

1. O sistema produz e persiste snapshots versionados (CSV/JSON) em `dados/` com metadados (timestamp, versão, checksum).
2. Existe um cache de snapshots que evita reprocessamento quando o snapshot não mudou (com TTL configurável).
3. A ingestão incremental processa apenas registros novos ou alterados desde o último snapshot conhecido.
4. Operações são idempotentes: reexecução não causa duplicação de dados no armazenamento canônico (SQLite/upsert).
5. Checksum (ex.: SHA256) é calculado e armazenado para cada snapshot; processo de ingest valida checksum antes de processar.
6. Há logs estruturados indicando decisões de cache, resultado da validação de checksum e contadores de registros processados.
7. Tests automatizados cobrindo: caso snapshot inalterado (cached), snapshot alterado (reprocess), e ingestão incremental com mudanças parciais.
8. Documentação curta (README ou seção no README existente) descrevendo flags/parametros CLI para forçar refresh, TTL e local de armazenamento.

> ✅ Todos os critérios acima foram implementados; consulte os módulos `src/ingest` e as novas opções de CLI, além dos testes em `tests/test_ingest_*` e as atualizações no README.

## Tasks / Subtasks

- [x] Implementar geração de snapshot (arquivo + metadados) e registro de checksum
  - [x] Calcular SHA256 do conteúdo do snapshot e salvar em metadados
- [x] Implementar camada de cache com TTL e verificação de checksum
  - [x] Implementar flag `--force-refresh` para ignorar cache
- [x] Implementar ingestão incremental com detecção de novos/alterados
  - [x] Implementar upsert idempotente no armazenamento canônico (SQLite)
- [x] Adicionar logs estruturados e métricas básicas (contadores processados)
- [x] Escrever testes unitários e integração para cenários principais
- [x] Atualizar documentação e exemplos de uso
- [x] Documentar o que foi implantado nessa etapa em `docs/sprint-reports` conforme definido no FR28 (`docs/planning-artifacts/prd.md`)

## Dev Notes

- Armazenamento dos snapshots: `dados/` (seguir convenção do repositório).
- Metadados esperados: `snapshot_id`, `generated_at`, `source_ticker` (quando aplicável), `rows_count`, `sha256`.
- Integração com pipeline existente: integrar à etapa de ingest (`src.dados_b3` / `src.retorno`) e usar conversões já existentes.
- Upsert: usar transações e índices apropriados para evitar race conditions; seguir padrão usado em `1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date`.
- Cache strategy: simples filesystem cache com TTL configurável via variável/env; considerar extensão futura para cache em memória ou redis.
- Logs: nível INFO para decisões de cache; nível DEBUG para diffs/parciais quando snapshot mudou.

### Project Structure Notes

- Código novo/alterado sugerido:
  - `src/dados_b3.py` — pontos de coleta e geração de snapshot
  - `src/ingest.py` (novo) — orquestra lógica de cache + ingestão incremental
  - `src/storage/sqlite_adapter.py` (ou adaptar `src.retorno`) — upsert e verificação de integridade
- Config: adicionar chaves em env/config para `SNAPSHOT_TTL`, `SNAPSHOT_DIR`, `FORCE_REFRESH`.

### References

- Sprint status: docs/implementation-artifacts/sprint-status.yaml (entry: `1-10-cache-de-snapshots-e-ingestao-incremental`)
- Histórica relacionada: `1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date`, `2-1-gerar-snapshot-csv-a-partir-de-dados-persistidos`, `2-2-calcular-sha256-e-registrar-metadados-do-snapshot`.

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

N/A

### Completion Notes List

- Ultimate context engine analysis (YOLO) aplicado: template preenchida com requisitos, critérios e tarefas.

### File List

- docs/implementation-artifacts/1-10-cache-de-snapshots-e-ingestao-incremental.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/112
