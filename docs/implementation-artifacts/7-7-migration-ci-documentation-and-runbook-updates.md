"""
# Story 7.7: migration-ci-documentation-and-runbook-updates

Status: ready-for-dev

## Story

As a Operador / DevOps / Tech Writer,
I want atualizar a documentação de migrações, CI gates e runbooks operacionais,
so that migrations possam ser executadas com segurança, validadas em CI e restauradas em caso de erro.

## Acceptance Criteria

1. Documentação de migrações presente em `docs/implantacao/migrations-runbook.md` com comandos claros: `migrations status`, `migrations apply`, `migrations rollback --to <id>` e exemplos de uso para SQLite.
2. CI inclui um job (ex.: `.github/workflows/ci.yml` ou `.github/workflows/migrations.yml`) que executa um `migrations --dry-run`/preflight e valida que a runbook descreve os passos usados pelo job.
3. Runbook contém checklist operacional (preflight checks, backups, verificação de snapshots/checksums, permissões de arquivo) e passos de restauração testados localmente com exemplos reproduzíveis.
4. Scripts de pré-check (`scripts/migrations/preflight_check.sh`) e rollback (`scripts/migrations/rollback_test.sh`) adicionados e documentados; CI executa rollback test em ambiente sandbox/mocked.
5. Atualização de `README.md` e `docs/playbooks/runbook-ops.md` apontando para o novo runbook e exemplos de comandos para recuperação e validação pós-migração.

## Tasks / Subtasks

- [ ] Task 1: Draft runbook `docs/implantacao/migrations-runbook.md`
  - [ ] Subtask 1.1: Document `migrations status/apply/rollback` examples for SQLite and recommended workflow
  - [ ] Subtask 1.2: Add preflight checklist (backup, snapshot, checksum verification, permissions)
- [ ] Task 2: Add preflight and rollback scripts under `scripts/migrations/`
  - [ ] Subtask 2.1: `preflight_check.sh` (checks DB availability, backups snapshots, verifies permissions)
  - [ ] Subtask 2.2: `rollback_test.sh` (creates temp DB, applies migration, rolls back, verifies schema_version)
- [ ] Task 3: CI integration
  - [ ] Subtask 3.1: Add/modify `.github/workflows/ci.yml` to include `migrations:preflight` job that runs scripts in CI (mocked environment)
  - [ ] Subtask 3.2: Add CI artifact publishing for migration logs and test DB snapshots
- [ ] Task 4: Docs linking and README updates
  - [ ] Subtask 4.1: Update `README.md` with runbook quick commands
  - [ ] Subtask 4.2: Update `docs/playbooks/runbook-ops.md` and `docs/implantacao/` index

## Dev Notes

- Arquitetura/constraints:
  - Projeto usa SQLite local por padrão; recomenda-se scripts leves para migrações e uso de tabela `schema_version` para rastrear versão.
  - Para MVP evitar `alembic` complexo sobre SQLite — preferir scripts idempotentes em `migrations/simple/` e um pequeno wrapper para `apply`/`rollback`.
  - Garantir que scripts conservem owner-only perms onde aplicável (`chmod 600 dados/data.db`) e documentar permissões no runbook.

- Testing & CI:
  - CI deve executar `preflight_check.sh` e `rollback_test.sh` em ambiente isolado (temporal DB) e publicar logs/artifacts para auditoria.
  - Validar que checksums de snapshots permanecem consistentes após migração (gerar snapshot antes e depois e comparar checksums).

### Project Structure Notes

- Arquivos recomendados a criar/editar:
  - docs/implantacao/migrations-runbook.md
  - scripts/migrations/preflight_check.sh
  - scripts/migrations/rollback_test.sh
  - migrations/simple/0001_init.sql (exemplo)
  - .github/workflows/ci.yml (adicionar job `migrations:preflight`)

### References

- Source: docs/planning-artifacts/epics.md (FR34, FR41, epic-7 entries)
- Source: docs/planning-artifacts/architecture.md (Migration Path, recommendations)
- Source: docs/planning-artifacts/prd.md (NFR-M1, FR41)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Created story file and updated sprint status to `ready-for-dev`.

### File List

- docs/implantacao/migrations-runbook.md (new - draft)
- scripts/migrations/preflight_check.sh (new - draft)
- scripts/migrations/rollback_test.sh (new - draft)

"""

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/161
