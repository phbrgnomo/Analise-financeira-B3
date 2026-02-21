---
title: Epic-1 - Discussão entre Agentes e Lista de Ações Consolidada
date: 2026-02-21
participants:
  - bmad-master
  - analyst (Mary)
  - architect (Winston)
  - dev (Amelia)
  - pm (John)
  - qa (Quinn)
  - quick-flow-solo-dev (Barry)
  - sm (Bob)
  - tech-writer (Paige)
  - ux-designer (Sally)
  - agent-builder (Bond)
  - module-builder (Morgan)
  - workflow-builder (Wendy)
  - tea (Murat)
---

Resumo da discussão:
- Todos os agentes concordam no diagnóstico: adaptadores e mapper estão sólidos, mas a persistência em SQLite (story 1-6) e a integração do pipeline (story 1-3) são lacunas críticas que impedem a validação completa do PRD.
- Riscos operacionais principais: concorrência em SQLite, ausência de migrações integradas, falta de smoke E2E no CI que valide checksum/snapshots.

Ações priorizadas (ordenadas por prioridade):

1) Implementar camada DB e upsert (P0)
   - Descrição: criar `src/db` com funções `upsert_prices`, `write_ingest_log`, `read_prices`.
   - Dono: dev (Amelia) / module-builder (Morgan)
   - Critério de aceitação: testes unitários que mostram idempotência (insert twice mantém contagem), integração em pipeline `--dry-run` passando.

2) Finalizar Schema (Story 1-11) e travar contrato canônico (P0)
   - Descrição: consolidar `docs/schema.json` e exemplos, adicionar ACs claras para mapeamento.
   - Dono: analyst (Mary) / pm (John) / tech-writer (Paige)
   - Critério: schema aprovado e commit referenciado por mapper; PRD atualizado.

3) Integrar persistência no pipeline (Story 1-6 + 1-3) (P0)
   - Descrição: pipeline.ingest deve executar: fetch → save_raw_csv → to_canonical → upsert_prices → generate snapshot.
   - Dono: quick-flow (Barry) / dev (Amelia)
   - Critério: `pipeline.ingest --dry-run` e `--force-refresh` testes mockados passam; snapshot gerado com checksum.

4) CI smoke job e checksum validation (P0)
   - Descrição: adicionar job CI que roda smoke E2E mockado e valida `.checksum` do snapshot; bloquear merge se falhar.
   - Dono: qa (Quinn) / tea (Murat)

5) Lock por ticker e testes de concorrência (P1)
   - Descrição: implementar mecanismo de lock simples (file-lock ou advisory) e testes que simulam execução concorrente por mesmo ticker.
   - Dono: architect (Winston) / qa (Quinn)

6) Migrations & DB init integration (P1)
   - Descrição: integrar `scripts/init_ingest_db.py` com comando `migrations apply` e garantir que pipeline detecte DB não inicializado com mensagem clara.
   - Dono: module-builder (Morgan) / dev (Amelia)

7) Documentação e playbooks (P0)
   - Descrição: tech-writer atualiza `docs/playbooks/quickstart-ticker.md`, adiciona `docs/phase-1-report.md` e guia de `migrations`/`init`.
   - Dono: tech-writer (Paige)

8) CLI UX e outputs (P1)
   - Descrição: imprimir resumo com job_id, filepath, raw_checksum, rows_fetched; adicionar `--metrics` flag.
   - Dono: ux (Sally) / dev (Amelia)

9) CI linters, remove __pycache__ e housekeeping (P1)
   - Descrição: garantir ruff/black em CI; adicionar `__pycache__` ao .gitignore se necessário.
   - Dono: sm (Bob) / dev (Amelia)

10) Nightly validation & backup/restore tests (P1)
    - Descrição: job noturno que valida integridade de snapshots e backups; teste de restore.
    - Dono: tea (Murat) / sm (Bob)

Observação final do orquestrador (bmad-master):
- Se aprovado, criar issues/PRs para cada item e atribuir os donos indicados; BMad Master pode orquestrar a execução em modo party-mode para acompanhar progresso e auxiliar em revisão de PRs.

Próximos passos sugeridos:
- Confirmar donos e prioridades; criar issues no tracker e iniciar Sprint com foco P0 (1-11, 1-6, CI smoke).
- Deseja que eu (BMad Master) crie as issues/PR templates para esses itens agora? (responda: sim / não / ajustar)
