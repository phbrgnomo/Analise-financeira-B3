---
generated: 2026-02-17T00:00:00Z
story_key: 2-5-politica-de-retencao-e-purge-de-snapshots
epic: 2
story_num: 5
status: ready-for-dev
owner: TBD
---

# Story 2.5: Política de Retenção e Purge de Snapshots

Status: ready-for-dev

## Story

Como Operador/DevOps,
quero uma política clara de retenção e um comando seguro de `purge` para snapshots,
para que o repositório/servidor mantenha uso de disco controlado mantendo auditação e possibilidade de restauração.

## Acceptance Criteria

1. Existe um registro de metadados para cada snapshot com: `path`, `ticker`, `created_at` (UTC), `rows`, `checksum_sha256`, `size_bytes`, `archived` (bool) e `retention_tier`.
2. A geração de snapshot (Story 2-1 / 2-3) grava metadados no registro e cria o arquivo em `snapshots/` com permissões adequadas.
3. Implementar comando CLI `snapshots.purge` com opções:
   - `--older-than DAYS` (ex.: `--older-than 90`)
   - `--keep-monthly N` (mantém N monthly rollups, ex.: 12)
   - `--keep-yearly N` (mantém N yearly rollups, ex.: 7)
   - `--archive-dir PATH` (opcional; padrão: `snapshots/archive/`)
   - `--dry-run` (lista candidatos sem excluir)
   - `--confirm` (executa exclusão)
4. O comando deve validar pré-condições antes de excluir:
   - Verificar checksum do arquivo e metadados correspondem
   - Se `archive-dir` fornecido, mover/validar cópia antes de remoção definitiva
   - Verificar permissões (somente usuário com permissão pode excluir)
5. Implementar política de retenção configurável via variável de ambiente `SNAPSHOT_RETENTION_POLICY` (JSON ou YAML curto) com valores padrão sensatos:
   - daily_keep_days: 90
   - keep_monthly: 12
   - keep_yearly: 7
   - min_free_space_mb: 1024 (aguardar confirmação em logs se limiar ultrapassado)
6. Implementar testes automatizados (unit + integração mocked):
   - Dry-run não modifica o estado
   - `--confirm` realmente remove arquivos e atualiza metadados
   - Arquivo arquivado é mantido e marcado em metadados
7. Documentação em `docs/playbooks/runbook-ops.md` explicando uso, exemplos e runbook para recuperação.

## Tasks / Subtasks

- [ ] Task 1: Definir e criar schema de metadados `snapshots` na DB (ou arquivo `metadata/snapshots.json`) - incluir migração.
  - [ ] Subtask 1.1: Especificar contrato de metadados e caminho padrão `snapshots/`.
- [ ] Task 2: Atualizar pipeline de geração de snapshot para gravar metadados (Story 2-1 / 2-3 integração).
- [ ] Task 3: Implementar CLI `snapshots.purge` (Typer) com flags e dry-run/confirm logic.
- [ ] Task 4: Implementar rotina de arquivamento seguro (move + checksum verify).
- [ ] Task 5: Escrever testes unitários para lógica de seleção/retention e integração para arquivos no FS (mock FS or tempdir).
- [ ] Task 6: Atualizar CI para incluir purge dry-run test (fast, mocked) e publicar artifact de teste.
- [ ] Task 7: Escrever documentação e exemplos de uso em `docs/playbooks/runbook-ops.md` e adicionar exemplos em `docs/playbooks/quickstart-ticker.md` se aplicável.

## Dev Notes

- Paths relevantes:
  - Snapshots: `snapshots/` (produzido por Story 2-1 / 2-3)
  - Archive: `snapshots/archive/` (opcional, configurável)
  - Metadados: `metadata/snapshots.db` (SQLite) ou `metadata/snapshots.json`
- Default retention policy (config via env `SNAPSHOT_RETENTION_POLICY`):
  ```yaml
  daily_keep_days: 90
  keep_monthly: 12
  keep_yearly: 7
  min_free_space_mb: 1024
  ```
- Implementation recommendations:
  - Use SQLite table `snapshots` for transactional updates and easy queries. Columns: `id, path, ticker, created_at, rows, checksum_sha256, size_bytes, archived BOOLEAN, retention_tier, archived_at`.
  - When purging, always perform `--dry-run` in CI and logging. Only `--confirm` deletes files.
  - Archive flow: copy file to `archive-dir`, verify checksum, then delete original and update metadata.
  - Provide idempotent behavior: repeated runs with same flags should produce same result (or no-op if already purged/archived).
  - Respect file permissions: prefer owner-only deletion and ensure process runs under correct user or verifies `os.geteuid()`.
  - Add telemetry/logging for purge actions (who, when, candidates, deleted_count, freed_bytes).

## Testing Requirements

- Unit tests for retention selection logic (boundary conditions, keep monthly/yearly logic).
- Integration tests using `tmp_path` to create fake snapshot files and metadata; test dry-run vs confirm.
- CI job: add a quick smoke test that runs `snapshots.purge --older-than 1 --dry-run` against a small fixture repository.

## Project Structure Notes

- Align with existing conventions: place CLI command implementation under `src/cli/snapshots.py` or `src/snapshots/cli.py` and expose via `main` entrypoint.
- Migration scripts under `src/db/migrations/` and referenced in docs.

## References

- Source: [docs/planning-artifacts/prd.md](docs/planning-artifacts/prd.md)
- Source: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md)
- Sprint tracking: [docs/implementation-artifacts/sprint-status.yaml](docs/implementation-artifacts/sprint-status.yaml)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Story scaffold criado com critérios, tarefas e notas de implementação.

### File List

- docs/implementation-artifacts/2-5-politica-de-retencao-e-purge-de-snapshots.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/127
