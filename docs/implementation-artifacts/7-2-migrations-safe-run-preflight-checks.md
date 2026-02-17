---
title: "7-2 Migrations: safe-run preflight checks"
story: 7-2-migrations-safe-run-preflight-checks
status: ready-for-dev
---

 # Story 7.2: migrations-safe-run-preflight-checks

 Status: ready-for-dev

 ## Story

 Como mantenedor/engenheiro de plataforma,
 quero executar verificações de pré-execução (preflight) seguras para migrações de banco de dados,
 para que migrações possam ser aplicadas com mínimo risco de corrupção de dados, perda de disponibilidade ou downtime.

 ## Acceptance Criteria

 1. Existe um comando/entrada `migrations preflight --target <env>` que executa todas as verificações sem aplicar mudanças.
 2. Preflight valida:
    - conectividade com o banco de dados alvo;
    - compatibilidade de esquema (colunas/tipos esperados);
    - ausência de locks ou transações longas que possam bloquear a migração;
    - checagem de versões/compatibilidade de drivers e dependências críticas;
    - checagem de espaço em disco, quota e limites de tabela (se aplicável);
    - validação de scripts idempotentes e detecta potenciais operações destrutivas (ex: DROP TABLE sem backup).
 3. Preflight retorna exit code != 0 em caso de falha, com mensagens de diagnóstico claras e arquivos de log legíveis.
 4. Preflight gera relatório resumido em formato `txt` e `json` contendo todas as verificações e resultados, com sugestões de mitigação.
 5. CI (pipeline) executa o preflight automaticamente antes de aceitar qualquer PR com mudanças de migração; PRs que falham no preflight são bloqueados.
 6. Documentação de operações (runbook) inclui passos de mitigação e rollback recomendados para cada tipo de falha identificada.

 ## Tasks / Subtasks

 - [ ] Implementar comando CLI `migrations preflight` (AC: 1,3)
   - [ ] Implementar checks de conectividade e versão do driver
   - [ ] Implementar análise estática dos scripts de migração (detectar DDL/DML perigosos)
   - [ ] Implementar checagens de recursos (espaço em disco, locks)
 - [ ] Gerar saída estruturada (`json`) e relatório legível (`txt`) (AC: 2,4)
 - [ ] Integrar preflight no pipeline CI (AC: 5)
 - [ ] Escrever runbook de operações e documentação para time (AC: 6)
 - [ ] Criar testes automatizados unitários e de integração (mocks para DB) (AC: 3)

 ## Dev Notes

 - Preferir implementação idempotente e não-destrutiva por padrão; checar flags explícitas para ações com risco.
 - Fornecer modo `--assume-yes` apenas para operadores humanos com autorização e logs adicionais.
 - Evitar executar migrações em horas críticas; integrar com janelas de manutenção definidas no runbook.
 - Telemetria: reportar métricas de preflight (tempo, checks falhos) para observability se existir infra.

 ### Project Structure Notes

 - Colocar implementação em `src/migrations/` seguindo padrão já adotado no projeto (modular, testável).
 - Expor comando via `src/main.py` entrypoint (se aplicável) e adicionar opção no CLI principal.
 - Testes em `tests/` com fixtures que mockam drivers/DB connections.

 ### References

 - Source hint: design de migrações e runbooks operacionais (adicionar links locais relevantes se existirem).

 ## Dev Agent Record

 ### Agent Model Used

 bmad-expert-simulated

 ### Debug Log References

 - logs/migrations-preflight-<timestamp>.log (implement after run)

 ### Completion Notes List

 - Análise inicial: requisitos de preflight definidos e tasks listadas.

 ### File List

 - docs/implementation-artifacts/7-2-migrations-safe-run-preflight-checks.md

 <!-- story_completion_status: ready-for-dev; ultimate context analysis completed -->
