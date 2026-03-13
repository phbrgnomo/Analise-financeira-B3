---
title: Phase 2 Report — Snapshots
created: 2026-03-11
---

# Resumo
Relatório operativo e checklist para o Epic 2 (Snapshots). Inclui comandos reproduzíveis, critérios de aceitação e playbooks de restauração e retenção.

**Objetivo:** consolidar as ações restantes, passos operacionais e comandos para validar/operar `pipeline snapshot`, `snapshots export`, `snapshots purge` e scripts CI.

**Pré-requisitos:** ambiente com `poetry` instalado; variáveis de ambiente conforme `.env.example`; migrations aplicadas.

**Comandos úteis**

- Aplicar migrations (local, usando um banco in-memory de teste):

```bash
poetry run python - << 'PY'
# the helper apply_migrations walks the `migrations/` directory and
# executes any pending SQL files after the current schema, so a fresh
# test database doesn’t need manual bootstrapping.
from src.db_migrator import apply_migrations
import sqlite3

conn = sqlite3.connect(':memory:')

# apply all pending migrations from 0000_init_schema.sql onward
apply_migrations(conn)
print('migrations applied')
PY
```

- Gerar snapshot para `TICKER`:

```bash
poetry run main snapshot --ticker PETR4 --output-dir snapshots/
```

- Exportar último snapshot (CSV ou JSON):

```bash
poetry run main snapshots export --ticker PETR4 --format csv --output snapshots/PETR4_export.csv
poetry run main snapshots export --ticker PETR4 --format json --output snapshots/PETR4_export.json
```

- Purge (retenção baseada em dias):

```bash
SNAPSHOT_RETENTION_DAYS=90 poetry run main snapshots purge --keep-days 90
```

- Verificar restauração/restore-verify:

```bash
poetry run main pipeline restore-verify --snapshot-path snapshots/PETR4_snapshot.csv
```

- Executar validação CI de checksums (script):

```bash
python3 scripts/ci_validate_checksums.py --db dados/data.db
```

- Rodar testes e lint localmente:

```bash
poetry install
poetry run pre-commit run --all-files
poetry run pytest -q
```


**Checklist de Aceitação (Phase 2)**

- [x] `migrations/0002_expand_snapshots.sql` presente e aplicada sem erros (teste de migração incluso)
- [x] `snapshots` table contém colunas: `snapshot_path`, `rows`, `checksum`, `job_id`, `size_bytes`, `archived`, `archived_at`
- [x] `pipeline snapshot --ticker <TICKER>` gera CSV com coluna `date` e sidecar `.checksum` (verificado por teste `test_snapshot_metadata`)
- [x] `record_snapshot_metadata()` persiste metadata com `checksum` igual ao valor de `sha256_file()` do arquivo gerado
- [x] `snapshots export` suporta `csv` e `json` e preserva metadados (`ticker`, `checksum`, `rows`)
- [x] `snapshots purge` aplica política configurável e atualiza `archived` + `archived_at` (retenção via var. de ambiente)
- [x] `pipeline restore-verify` valida integridade do snapshot vs metadados (checksum)
- [x] `scripts/ci_validate_checksums.py` executa em CI e retorna exit code != 0 em mismatch (testado pela suíte)
- [x] Testes pytest para todas as 6 stories existentes e pipeline completo passam no CI (rodados localmente, saída 0)
- [x] Documentação operativa criada: este arquivo + exemplos em `docs/playbooks/quickstart-ticker.md`


**Runbook de Restauração (passos rápidos)**

1. Localizar snapshot a restaurar (DB `snapshots` → `snapshot_path`).
2. Verificar sidecar checksum:

```bash
sha256sum snapshots/PETR4_snapshot.csv
cat snapshots/PETR4_snapshot.csv.checksum
```

3. Executar `restore-verify` para checar integridade e simular ingest (veja o exemplo na seção **Comandos úteis**, onde o mesmo comando é apresentado).

4. Se validado, importar CSV para DB de staging seguindo o processo de ingest (adotar fluxo `db.write_prices()` com conn de staging) e rodar checks (row counts, amostras de valores).

5. Pós-restore: atualizar `snapshots` metadata se necessário e registrar evidência (`.sisyphus/evidence/restore-<timestamp>.txt`).


**Notas Operacionais e Recomendações**

- Unificar checksum: usar `sha256_file()` como fonte de verdade para todos os registros e CI. Remover ou documentar qualquer outro método de hashing. A geração de sidecar `.checksum` já é feita por `write_snapshot()` e existe teste `test_snapshot_metadata` cobrindo sua criação.
- Garantir que `apply_migrations()` é parte do bootstrap do ambiente CI antes de rodar testes que dependem do schema expandido. Os testes atuais já chamam `apply_migrations()` e validam o comportamento da migração 0002; além disso, o workflow CI agora contém passos explícitos (jobs **test** e **integration**) que aplicam as migrações no banco padrão (`dados/data.db`) antes de executar qualquer comando.
- Adicionar `SNAPSHOT_RETENTION_DAYS` ao `.env.example` e documentar seu uso — as funções de retenção (`get_retention_days`) leem esta variável com fallback para 90.
- Documentar limites operacionais do uso de SQLite (concorrência por ticker, datasets grandes) em `docs/architecture.md`.
- Incluir um teste de migração que aplica `0002_expand_snapshots.sql` em um DB existente (dump) para evitar regressões em ambientes reais; já implementado nas suítes de teste existentes.


**Evidências & Onde olhar**

- Planejamento e Req: `docs/planning-artifacts/epics.md`
- Epic 2 plan: `.sisyphus/plans/epic-2-snapshots.md`
- Learnings/evidences: `.sisyphus/notepads/epic-2-snapshots/learnings.md`
- Implementação: `src/pipeline.py`, `src/db/snapshots.py`, `src/snapshot_cli.py`, `scripts/ci_validate_checksums.py`
