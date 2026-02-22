---
title: Sprint Planning - Epic 1 (Ingestão & Persistência)
date: 2026-02-19
epic: Epic-1
---

# Sprint Planning — Epic 1: Ingestão idempotente e persistência

Objetivo: entregar ingestão idempotente por ticker (adapter yfinance), mapeamento canônico, persistência (prices + returns), pipeline CLI básico e snapshots auditáveis.

**Histórias (Resumo & Prioridade)**
- `1-11` Definir esquema canônico e documentação — Prioridade: P0
- `1-1` Implementar interface de Adapter e adaptador yfinance (mínimo) — Prioridade: P0
- `1-6` Persistir dados canônicos no SQLite com upsert por (ticker, date) — Prioridade: P0
- `1-7` Transformação de retornos e persistência em `returns` — Prioridade: P0
- `1-3` Implementar comando pipeline / orquestrador CLI básico — Prioridade: P0
- `1-4` Salvar resposta bruta do provedor e registrar metadados — Prioridade: P1
- `1-8` Implementar retries/backoff no adaptador crítico — Prioridade: P1
- `1-2` Implementar Canonical Mapper (provider → schema canônico) — Prioridade: P1
- `1-5` Validar estrutura CSV / filtrar linhas inválidas — Prioridade: P1
- `1-9` Garantir execução concorrente segura (lock por ticker simples) — Prioridade: P2
- `1-10` Cache de snapshots e ingestão incremental — Prioridade: P2

**Blockers (dependências principais)**
- `1-11` → bloqueia `1-2` e `1-6` (schema must be defined before mapper and persistence).
- `1-1` → bloqueia `1-3`, `1-4`, `1-8` (adapter mínimo required for pipeline, raw save and retries).
- `1-2` → bloqueia `1-5` e `1-6` (mapper needed to normalize before validate/persist).
- `1-6` → bloqueia `1-7` e `1-10` (returns and snapshots require persisted prices).
- `1-3` depende de `1-1`, `1-2`, `1-6` (integra os módulos implementados).

- **Grupos que podem ser executados em paralelo**
- Grupo A (inicial, paralelo): `1-11`, `1-1` — definir schema; criar adaptador básico.
   - Observação: `1-4` e `1-8` dependem de `1-1` e devem ser implementadas imediatamente após a entrega do adaptador.
    - Após conclusão de `1-1`, executar (sequencialmente ou em curto ciclo): `1-4`, `1-8` — raw save e retries/backoff (melhor como melhorias incrementais do adaptador).
- Grupo B (após A): `1-2`, `1-5` — canonical mapper e validação/filtragem.
- Grupo C: `1-6`, `1-9` — persistência SQLite (upsert) e locks por ticker (integração posterior).
- Grupo D: `1-7`, `1-10` — cálculo de retornos e cache/snapshots.
- Grupo E (integração final): `1-3` — pipeline CLI que orquestra todo o fluxo.

**Sequência de implementação recomendada (sprint)**
1. Sprint start — Paralelo (Grupo A):
   - Implementar `1-11` (DDL mínima + doc do schema).
   - Implementar `1-1` (adapter yfinance minimal fetch → DataFrame).
2. Após `1-1` entregue (curto ciclo):
   - Implementar `1-4` (salvar raw response em `raw/<provider>/` com checksum) — melhoria do adaptador.
   - Implementar `1-8` (retries/backoff básicos no adaptador) — melhoria do adaptador.
2. Assim que `1-11` e `1-1` tiverem entregáveis:
   - Paralelo (Grupo B): `1-2` (canonical mapper) e `1-5` (validação CSV/pandera).
3. Em seguida (Grupo C):
   - `1-6` Persistência SQLite com upsert por `(ticker,date)` e metadados (`source`, `fetched_at`).
   - `1-9` Implementação leve de lock por ticker (file lock ou mutex DB).
4. Após persistência:
   - `1-7` Calcular retornos diários e persistir em `returns`.
   - `1-10` Implementação POC de snapshot + checksum e ingest incremental.
5. Integração final (Grupo E):
   - `1-3` Pipeline CLI `ingest --ticker` que faz: lock → fetch(raw) → map → validate → persist → returns → snapshot → unlock.
   - Escrever testes E2E mockados e quickstart docs.

**Riscos e mitigação rápida**
- Divergência de schema provedor ↔ canônico: mitigar definindo `1-11` clara + exemplos de mapeamento e testes de mapeamento.
- Testes que chamam provedores reais em CI: mitigar com mocks/fixtures (architecture.md recomenda). Não executar chamadas reais em CI.
- Corrupção por concorrência no SQLite: mitigar com `1-9` lock simples e testes de concorrência dirigidos.

**Entregáveis MVP deste sprint**
- Adapter yfinance funcional com raw save e retries básicos.
- Schema canônico documentado e `canonical mapper` implementado.
- Persistência SQLite (`prices`) com upsert; cálculo e persistência de `returns`.
- Pipeline CLI básico que gera snapshot CSV + checksum para um ticker.
- Testes unitários e um teste de integração quickstart (mocked).

**Próximos passos sugeridos**
1. Criar issues detalhadas por história (templates com acceptance criteria).
2. Implementar os itens do Grupo A em paralelo (atribuir responsáveis).
3. Após entrega de A, iniciar Grupo B e seguir sequência.

--
Arquivo gerado automaticamente a partir do planejamento de Epic-1.
