## Story 7.1: escolher-e-integrar-ferramenta-de-migracoes-ou-script-simples

Status: ready-for-dev

## Story

As a Developer/Operator,
I want escolher e integrar uma ferramenta de migrações ou um conjunto de scripts simples,
so that o projeto mantenha `schema_version`, aplique migrações versionadas e suporte rollback seguro para o banco local.

## Acceptance Criteria

1. Existe uma estratégia documentada (ferramenta: ex. Alembic ou scripts simples) com justificativa técnica e limitações para SQLite.
2. Implementar mecanismo inicial de migração que cria/atualiza tabela `schema_version` e aplica ao menos a migração inicial (schema base: `prices`, `returns`, `ingest_logs`, `snapshots`, `metadata`).
3. Fornecer comandos CLI (ex.: `migrations status|apply|rollback`) ou scripts equivalentes para aplicar e reverter migrações localmente.
4. Antes de aplicar migração na base de dados, existe um preflight check automático que cria um backup (dump) em `snapshots/migrations-backups/` com timestamp.
5. Testes unitários cobrem: aplicação da migração inicial, verificação de `schema_version`, e rollback básico; CI valida preflight em um job leve.
6. Documentação e runbook incluídos em `docs/planning-artifacts` descrevendo procedimento de upgrade/rollback e limitações (SQLite: locks, concorrência).

## Tasks / Subtasks

- [ ] Avaliar opções: Alembic vs scripts SQL versionados (prós/cons para SQLite)
- [ ] Definir convenção de versão (timestamp vs incremental) e naming pattern para arquivos de migração
- [ ] Criar pasta `migrations/` com migração inicial `0001_create_base_schema.sql` ou equivalente Alembic
- [ ] Implementar CLI mínimo `poetry run main migrations status|apply|rollback` ou script `scripts/migrate.py`
- [ ] Implementar preflight backup (export DB copy) antes de aplicar migrations
- [ ] Escrever testes que apliquem e revertam a migração em um DB temporário
- [ ] Adicionar documentação `docs/planning-artifacts/migrations.md` e trecho no README

## Dev Notes

- Arquitetura e restrições: Banco primário é SQLite (`dados/data.db`) — ALTA cautela: SQLite tem limitações em migrações concorrentes; preferir operações atômicas e backups antes de alterações destrutivas.
- Recomenda-se: usar scripts SQL idempotentes ou Alembic com backend SQLite; se optar por Alembic, documentar que migrations com operações DDL complexas podem falhar em SQLite e exigir passos manuais.
- Backup pré-aplicação: copiar `dados/data.db` para `snapshots/migrations-backups/<timestamp>-dados.db` com `chmod 600`.
- Para rollback em SQLite: manter scripts de reversão explícitos sempre que possível; documentar cenários onde rollback automático não é garantido.
- Arquivos de migração: usar `migrations/` com prefixo incremental ou timestamp, ex.: `0001_init.sql` ou `20260217_0001_create_base_schema.sql`.

### Project Structure Notes

- Nova pasta: `migrations/` (controlada por VCS)
- CLI: extensão em `src/main.py` para subcomando `migrations`
- Scripts auxiliares: `scripts/migrate.py` (opcional) com helpers para backup e apply/rollback

### Testing Requirements

- Test runner: pytest. Adicionar testes em `tests/test_migrations.py` que usam um DB temporário (tempfile) para aplicar/rollback.
- CI: job leve que executa `pytest -q tests/test_migrations.py` e executa preflight check (dry-run) antes de aceitar PRs que modificam migrations.

### References

- Source: docs/planning-artifacts/epics.md (FR34, FR41 — migrações versionadas e rollback)
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml
- Arquitetura: docs/planning-artifacts/architecture.md (ver seção de DB / deploy se aplicável)

## Dev Agent Record

### Agent Run

- Run mode: automated (workflow execution)
- Completion Notes: Análise inicial realizada; arquivos criados/atualizados: `migrations/` (placeholder), story file e sprint-status atualizado.

### File List

- docs/implementation-artifacts/7-1-escolher-e-integrar-ferramenta-de-migracoes-ou-script-simples.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/155
