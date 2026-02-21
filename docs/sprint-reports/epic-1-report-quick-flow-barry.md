---
title: Epic-1 - Relatório Quick Flow (Barry)
agent: Barry (quick-flow-solo-dev)
role: Quick Flow Solo Dev
date: 2026-02-21
---

Resumo executivo (ação rápida):
- Entregas práticas e imediatas para fechar o MVP do Epic-1 com baixo atrito.

Checklist mínimo para um PR rápido:
1. Implementar `src/db/` com função `upsert_prices(df, ticker)` e teste unitário simples (mock SQLite in-memory).
2. Integração no pipeline: chamar `upsert_prices` após `to_canonical` em pipeline.ingest (flag --dry-run para testes).
3. Pequeno script de migração que cria tabela `prices` e `ingest_logs` (script: scripts/init_ingest_db.py já existe, integrar no CI).
4. Corrigir guardrail de normalização de ticker (evitar double-suffix).

Sugestão de PRs incrementais (prioridade):
- PR A: `src/db` + migration init (1-2 dias)
- PR B: pipeline integration + dry-run tests (1 dia)
- PR C: CI smoke job (1 dia)

Observação: separar commits pequenos e testáveis para review rápido; objetivo: demonstrar persistência em SQLite com upsert e passar o smoke E2E mockado.
