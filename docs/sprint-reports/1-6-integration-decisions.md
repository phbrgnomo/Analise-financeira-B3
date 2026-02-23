# Story 1.6 / Epic-1 — Integração: decisões e notas operacionais

**Data:** 2026-02-22

Este documento resume as decisões tomadas ao integrar a persistência canônica
(Story 1.6) com a validação (Story 1.5) e opera como runbook para
implementações/ops.

## Decisões chave

- Checksum canônico: per-row
  - O projeto adota checksum per-row como valor canônico para detectar
    alterações linha-a-linha. A função `row_checksum_from_series` está
    centralizada em `src/utils/checksums.py`.
  - O sistema continua a gravar também o checksum do arquivo bruto (`*.checksum`)
    para identificar o artefato de origem; ambos os valores podem ser úteis,
    dependendo do caso de uso.

- Ingest logs: JSON-only
  - As entradas de ingestão são persistidas como JSON em
    `metadata/ingest_logs.json` (array de entradas). Isso mantém um histórico
    auditável e evita a necessidade de sincronizar esquemas DB separados.
  - Chamadas previas que inseriam `ingest_logs` no DB foram transformadas em
    *no-op* (shim) para evitar efeitos colaterais e permitir uma migração
    futura, caso desejado.

## Mudanças aplicadas no código

- `src/utils/checksums.py`
  - Nova função `row_checksum_from_series` para cálculo canônico per-row.

- `src/ingest/pipeline.py`
  - Mantém o checksum do arquivo bruto (`raw_checksum`) e adiciona
    `per_row_checksums` no registro de metadados JSON.

- `src/validation.py`
  - Persiste entradas de ingest e erros para `metadata/ingest_logs.json` e
    não escreve mais uma linha de auditoria no DB.

- `src/db.py`
  - `insert_ingest_log` é um shim sem efeitos (loga aviso). A definição da
    tabela `ingest_logs` foi mantida como metadado durante a transição, mas
    a criação da tabela via `scripts/init_ingest_db.py` foi alterada para
    não criar `ingest_logs` (cria `metadata` em vez disso).
  - Exposição de tuning via variáveis de ambiente (PRAGMAs e retry):
    - `DB_JOURNAL_MODE` (default `WAL`)
    - `DB_BUSY_TIMEOUT_MS` (default `500`)
    - `DB_MAX_RETRIES` (default `5`)
    - `DB_BASE_RETRY_DELAY` (default `0.05`)

- `src/ingest/runner.py`
  - Novo wrapper `run_write_with_validation` que força a execução da validação
    antes de gravar as linhas válidas no DB (evita bypass acidental).

- `scripts/init_ingest_db.py`
  - Atualizado para criar tabela `metadata` (key/value) ao invés de
    `ingest_logs`, evitando conflito de esquema.

## Testes adicionados

- `tests/integration/test_e2e_full_flow.py` — valida o fluxo completo:
  `save_raw_csv` → `to_canonical` → `run_write_with_validation` → leitura da
  tabela `prices` e verificação de `metadata`.

- `tests/integration/test_init_ingest_db_schema_match.py` — garante que o
  script de inicialização cria a tabela `metadata` compatível.

## Operações e recomendações

- CI: adicionar job matrix para validar com versões diferentes do SQLite
  (para garantir comportamento do fallback em runtimes antigas).

- Tuning: em ambientes com muitos escritores simultâneos aumente
  `DB_BUSY_TIMEOUT_MS` e `DB_MAX_RETRIES`. Para cargas elevadas, considere
  mover para um banco que suporte melhor concorrência (Postgres) ou usar um
  mecanismo de fila para coordenar atualizações.

- Migração futura: se houver necessidade de mover ingest logs para DB,
  definir claramente um passo de migração que copie `metadata/ingest_logs.json`
  para a nova tabela, atualizar os consumidores e remover o shim `insert_ingest_log`.

## Observabilidade

- Recomenda-se adicionar métricas para:
  - contagem de writes falhados/retentativas (`_db_metrics` já provê alguns
    contadores básicos),
  - latência média de writes,
  - número de entradas de ingest inválidas por intervalo de tempo.

## Próximos passos

1. Atualizar documentação operacional (`docs/runbooks/`) com instruções de
   tuning por ambiente.
2. Decidir sobre migração de ingest logs para DB (se necessário) e criar
   roteiro de migração.
3. Considerar remoção do código legado relacionado a `ingest_logs` no DB
   após migração completa.

---

Documento gerado automaticamente durante integração de Story 1.6 com epic-1.

*** End Patch
