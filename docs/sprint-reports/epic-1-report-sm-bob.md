---
title: Epic-1 - Relatório Scrum Master (Bob)
agent: Bob (sm)
role: Scrum Master
date: 2026-02-21
---

Objetivo de coordenação:
- Remover bloqueios, priorizar iterações e organizar o próximo sprint para entregar 1-11 e 1-6.

Principais bloqueadores identificados:
- Dependência técnica: 1-11 (schema) não consolidada — bloqueia mapper/persistence.
- Falta de integração de DB e migrações automatizadas (scripts existents mas não integrados no CI).

Plano sugerido para próximo sprint (2 semanas):
1. Sprint Goal: entregar 1-11 e 1-6, com CI smoke (mocked) para quickstart.
2. Tasks: 2 devs (1 backend adapter/db + 1 dev mapper/pipeline), 1 QA para testes de integração, tech-writer para atualizar docs.
3. Definition of Done: upsert implementado, migration script na repo, CI job passando com smoke E2E mockado e docs atualizados.

Risco e mitigação:
- Risco: concorrência em SQLite — mitigação: adicionar lock por ticker e test de concorrência no sprint.
- Risco: mudança de schema tardia — mitigação: travar schema mínimo e criar migração incremental.

Comentários: priorizar bloqueios técnicos antes de add funcionalidades não-críticas.
