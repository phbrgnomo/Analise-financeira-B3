# Epic 2 — Snapshots: Geração, Validação, Exportação, Retenção e Restauração

## TL;DR

> **Quick Summary**: Implementar as 6 stories do Epic 2 para o pipeline de snapshots: geração de CSV a partir de dados persistidos, registro de checksum/metadados, exportação CLI (CSV/JSON), validação CI de checksums, política de retenção/purge, e verificação de restauração.
>
> **Deliverables**:
> - Comando CLI `pipeline snapshot` para gerar snapshot CSV de dados canônicos (Story 2-1)
> - Coluna `checksum` + metadados expandidos na tabela `snapshots` + registro automático (Story 2-2)
> - Comando CLI `snapshots export` com saída CSV/JSON + metadados (Story 2-3)
> - Script CI para validação de checksums de snapshots (Story 2-4)
> - Comando CLI `snapshots purge` com política de retenção configurável (Story 2-5)
> - Comando CLI `pipeline restore-verify` para verificar integridade de restauração (Story 2-6)
> - Testes pytest para todas as 6 stories
> - Migração SQL para expandir schema da tabela `snapshots`
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 3 waves + final verification
> **Critical Path**: Task 1 (migration) → Task 3 (snapshot gen) → Task 7 (export) → Task 11 (purge) → Task 13 (restore-verify)

---

## Context

### Original Request
Implementar todas as 6 stories do Epic 2 (2-1 a 2-6) localizadas em `docs/implementation-artifacts/2-*.md`.

### Interview Summary
**Key Discussions**:
- **Migration strategy**: Usar `db_migrator.py` (SQL files + `schema_migrations` table) para novas colunas. NÃO usar PRAGMA user_version.
- **Checksum approach**: Usar `sha256_file()` (hash de bytes do arquivo) para registro de metadados — consistente com `checksums.json` manifest.
- **CLI structure**: Seguir padrão flat existente em `src/` (sem criar `src/cli/`). Montar sub-apps via `app.add_typer()` em `src/main.py`.
- **Retention model**: Simplificar para 2 estados: `active` e `archived` (boolean). Sem multi-tier (hot/warm/cold).
- **Scope exclusions**: Sem REST API, sem monitoramento de disco, sem SQLAlchemy.
- **Inline CREATE TABLE**: Remover de `_upsert_snapshot_metadata()` após migração expandir schema.
- **JSON orientation**: Usar `records` para output JSON.
- **Test strategy**: Tests-after (pytest), reutilizando fixtures existentes (`sample_db`, `snapshot_dir`, `create_prices_db_from_csv()`).

**Research Findings**:
- `write_snapshot()` já retorna SHA256 digest e escreve `.checksum` sidecar — Story 2-2 parcialmente implementada.
- `_prune_old_snapshots()` já faz retenção básica (keep N latest) — Story 2-5 estende isso.
 - `snapshots ingest` (em `src/ingest_cli.py`) faz CSV→DB (direção oposta de Story 2-1 que é DB→CSV).
- Duas mechanisms de checksum coexistem: `sha256_file()` vs `serialize_df_bytes()`.
- `_upsert_snapshot_metadata()` gera `job_id` via SHA256 se não fornecido — importante para idempotência.

### Metis Review
**Identified Gaps** (all addressed):
- Migration strategy ambiguity → Use SQL file migration via `db_migrator.py`
- Checksum approach conflict → Use `sha256_file()` for metadata consistency
- Scope creep risks (API, disk monitoring, multi-tier retention) → All excluded
- Missing acceptance criteria for edge cases → All resolved with concrete behavior
- SQLAlchemy references in specs → Ignored, project uses raw sqlite3
- CLI path convention conflict → Follow existing flat pattern

---

## Work Objectives

### Core Objective
Entregar pipeline completo de snapshots: gerar a partir de dados persistidos, registrar metadados com checksum, exportar em múltiplos formatos, validar em CI, aplicar retenção, e verificar restauração.

### Concrete Deliverables
- `migrations/0002_expand_snapshots.sql` — Schema migration para expandir tabela `snapshots`
- `src/db/snapshots.py` — Funções expandidas de DB para snapshots (query, metadata, purge)
- `src/pipeline.py` — Comandos `snapshot` e `restore-verify`
- `src/snapshot_cli.py` — Sub-app Typer para `snapshots export` e `snapshots purge`
- `src/main.py` — Montagem do novo sub-app `snapshots`
- `src/etl/snapshot.py` — Export JSON, metadata enriquecido
- `src/retention.py` — Lógica de política de retenção
- `scripts/ci_validate_checksums.py` — Script de validação CI
- 6 arquivos de teste pytest (1 por story)

### Definition of Done
- [ ] `poetry run pytest` → todos os testes passam (0 falhas)
- [ ] `poetry run pre-commit run --all-files` → sem erros
- [ ] Todos os 6 comandos CLI executam sem erro com dados válidos
- [ ] Migração `0002_expand_snapshots.sql` aplica sem erro em DB existente

### Must Have
- Todas as acceptance criteria das 6 stories atendidas
- Checksum SHA256 registrado para todo snapshot gerado
- Idempotência: re-gerar snapshot para mesmo ticker/período não duplica metadados
- Exit code 1 + mensagem de erro para ticker inexistente ou range vazio
- Testes pytest para cada story
- Output via `CliFeedback` (sem `print()`/`typer.echo()` direto)
- Line length ≤ 88 chars (ruff config)

### Must NOT Have (Guardrails)
- ❌ REST API / endpoints HTTP (nenhum framework HTTP existe no projeto)
- ❌ SQLAlchemy (projeto usa `sqlite3` raw)
- ❌ Diretório `src/cli/` (seguir padrão flat existente)
- ❌ Multi-tier retention (hot/warm/cold) — apenas `active`/`archived`
- ❌ Monitoramento de espaço em disco (`min_free_space_mb`)
- ❌ Modificação de dados em `dados/data.db` durante testes
- ❌ `print()` ou `typer.echo()` direto — usar `CliFeedback`
- ❌ Linhas > 88 caracteres
- ❌ Comentários excessivos / docstrings genéricos / over-abstraction
- ❌ `CREATE TABLE IF NOT EXISTS` inline em funções de DB (remover o existente)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (tests-after — write impl first, then tests)
- **Framework**: pytest
- **Test command**: `poetry run pytest`
- **Lint command**: `poetry run pre-commit run --all-files`

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **CLI commands**: Use Bash — Run command, validate stdout/stderr, check exit code
- **DB operations**: Use Bash (python REPL) — Query DB, verify schema/data
- **File operations**: Use Bash — Check file exists, validate content/checksum
- **CI scripts**: Use Bash — Run script, check exit code and output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — start immediately, MAX PARALLEL):
├── Task 1: Schema migration 0002_expand_snapshots.sql [quick]
├── Task 2: Expand src/db/snapshots.py with new DB functions [unspecified-high]
├── Task 3: Implement pipeline snapshot command (Story 2-1) [deep]
├── Task 4: Integrate checksum metadata registration (Story 2-2) [deep]
├── Task 5: Tests for Story 2-1 [unspecified-high]
└── Task 6: Tests for Story 2-2 [unspecified-high]

Wave 2 (Export + CI — after Wave 1):
├── Task 7: Implement snapshots export CLI (Story 2-3) [deep]
├── Task 8: Implement CI validation script (Story 2-4) [unspecified-high]
├── Task 9: Tests for Story 2-3 [unspecified-high]
└── Task 10: Tests for Story 2-4 [unspecified-high]

Wave 3 (Retention + Restore — after Wave 2):
├── Task 11: Implement retention policy + purge CLI (Story 2-5) [deep]
├── Task 12: Tests for Story 2-5 [unspecified-high]
├── Task 13: Implement restore-verify CLI (Story 2-6) [deep]
└── Task 14: Tests for Story 2-6 [unspecified-high]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit [oracle]
├── Task F2: Code quality review [unspecified-high]
├── Task F3: Full CLI QA — all 6 commands [unspecified-high]
└── Task F4: Scope fidelity check [deep]

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → Task 7 → Task 11 → Task 13 → F1-F4
Parallel Speedup: ~55% faster than sequential
Max Concurrent: 6 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 (migration) | — | 2, 3, 4, 5, 6 | 1 |
| 2 (db functions) | 1 | 3, 4, 7, 8, 11, 13 | 1 |
| 3 (snapshot cmd) | 1, 2 | 5, 7, 8 | 1 |
| 4 (checksum meta) | 1, 2, 3 | 6, 7, 8 | 1 |
| 5 (tests 2-1) | 3 | — | 1 |
| 6 (tests 2-2) | 4 | — | 1 |
| 7 (export CLI) | 2, 3, 4 | 9 | 2 |
| 8 (CI validation) | 2, 3, 4 | 10 | 2 |
| 9 (tests 2-3) | 7 | — | 2 |
| 10 (tests 2-4) | 8 | — | 2 |
| 11 (purge CLI) | 2, 4 | 12 | 3 |
| 12 (tests 2-5) | 11 | — | 3 |
| 13 (restore-verify) | 2, 3 | 14 | 3 |
| 14 (tests 2-6) | 13 | — | 3 |
| F1-F4 (final) | ALL | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: **6 tasks** — T1 → `quick`, T2 → `unspecified-high`, T3 → `deep`, T4 → `deep`, T5 → `unspecified-high`, T6 → `unspecified-high`
- **Wave 2**: **4 tasks** — T7 → `deep`, T8 → `unspecified-high`, T9 → `unspecified-high`, T10 → `unspecified-high`
- **Wave 3**: **4 tasks** — T11 → `deep`, T12 → `unspecified-high`, T13 → `deep`, T14 → `unspecified-high`
- **FINAL**: **4 tasks** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Schema Migration — Expand `snapshots` Table (Story 2-2 foundation)

  **What to do**:
  - Create `migrations/0002_expand_snapshots.sql` with ALTER TABLE statements to add columns: `snapshot_path TEXT`, `rows INTEGER`, `checksum TEXT`, `job_id TEXT`, `size_bytes INTEGER`, `archived BOOLEAN DEFAULT 0`, `archived_at TEXT`
  - Each ALTER TABLE must be a separate statement (SQLite limitation — one column per ALTER)
  - Remove inline `CREATE TABLE IF NOT EXISTS snapshots` from `src/db/snapshots.py:_upsert_snapshot_metadata()` — the table is already created by `migrations/0000_init_schema.sql`
  - Keep the `CREATE INDEX IF NOT EXISTS` statement (idempotent, safe to keep)
  - Verify migration applies cleanly on a fresh DB (run `apply_migrations()`)
  - Verify migration applies cleanly on an existing DB with the old schema

  **Must NOT do**:
  - Do NOT use PRAGMA user_version — use `db_migrator.py` SQL file system
  - Do NOT drop or recreate the `snapshots` table — ALTER only
  - Do NOT touch `migrations/0000_init_schema.sql` or `migrations/0001_create_returns.sql`
  - Do NOT add `retention_tier TEXT` column — we use boolean `archived` only

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single SQL file creation + small edit in one Python file. Clear, bounded scope.
  - **Skills**: `[]`
    - No special skills needed for SQL migration + Python edit.

  **Parallelization**:
  - **Can Run In Parallel**: NO — other Wave 1 tasks depend on this
  - **Parallel Group**: Wave 1 (first to complete)
  - **Blocks**: Tasks 2, 3, 4, 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `migrations/0000_init_schema.sql` — Existing migration format, table creation pattern, current `snapshots` schema (id, ticker, created_at, payload)
  - `migrations/0001_create_returns.sql` — Second migration example showing SQL file convention
  - `src/db_migrator.py:57-95` — `apply_migrations()` function: reads SQL files from `migrations/` dir, tracks applied ones in `schema_migrations` table, applies in alphabetical order

  **Files to Modify**:
  - `src/db/snapshots.py:73-80` — Remove the `CREATE TABLE IF NOT EXISTS snapshots` block from `_upsert_snapshot_metadata()`. Keep the `CREATE INDEX IF NOT EXISTS` on line ~82.

  **WHY Each Reference Matters**:
  - `0000_init_schema.sql` shows the exact current schema you're ALTERing — you must know what columns already exist
  - `0001_create_returns.sql` shows naming convention: `{sequence}_{description}.sql`
  - `db_migrator.py` shows how migrations are discovered and applied — your file must be in `migrations/` dir with correct naming

  **Acceptance Criteria**:
  - [ ] File `migrations/0002_expand_snapshots.sql` exists with 7 ALTER TABLE statements
  - [ ] `CREATE TABLE IF NOT EXISTS snapshots` removed from `src/db/snapshots.py`
  - [ ] `CREATE INDEX IF NOT EXISTS` still present in `src/db/snapshots.py`
  - [ ] Migration applies on fresh DB: `poetry run python -c "from src.db.connection import connect, init_db; conn = connect(':memory:'); init_db(conn)"` → no errors

  **QA Scenarios**:

  ```
  Scenario: Migration applies on fresh in-memory DB
    Tool: Bash
    Preconditions: No DB exists
    Steps:
      1. Run: poetry run python -c "
         import sqlite3
         from src.db_migrator import apply_migrations
         conn = sqlite3.connect(':memory:')
         conn.executescript(open('migrations/0000_init_schema.sql').read())
         conn.executescript(open('migrations/0001_create_returns.sql').read())
         apply_migrations(conn)
         cols = [r[1] for r in conn.execute('PRAGMA table_info(snapshots)').fetchall()]
         print('COLUMNS:', cols)
         assert 'checksum' in cols, f'checksum missing: {cols}'
         assert 'snapshot_path' in cols, f'snapshot_path missing: {cols}'
         assert 'rows' in cols, f'rows missing: {cols}'
         assert 'size_bytes' in cols, f'size_bytes missing: {cols}'
         assert 'archived' in cols, f'archived missing: {cols}'
         assert 'archived_at' in cols, f'archived_at missing: {cols}'
         assert 'job_id' in cols, f'job_id missing: {cols}'
         print('PASS: all columns present')
         "
      2. Verify exit code is 0
    Expected Result: All 7 new columns present in snapshots table, exit code 0
    Failure Indicators: KeyError, sqlite3.OperationalError, missing column name
    Evidence: .sisyphus/evidence/task-1-migration-fresh-db.txt

  Scenario: Inline CREATE TABLE removed from snapshots.py
    Tool: Bash
    Preconditions: Task completed
    Steps:
      1. Run: grep -n "CREATE TABLE IF NOT EXISTS snapshots" src/db/snapshots.py
      2. Verify exit code is 1 (no match found)
      3. Run: grep -n "CREATE INDEX IF NOT EXISTS" src/db/snapshots.py
      4. Verify exit code is 0 (index creation still present)
    Expected Result: No CREATE TABLE match, but CREATE INDEX still exists
    Failure Indicators: grep finds CREATE TABLE line, or CREATE INDEX is missing
    Evidence: .sisyphus/evidence/task-1-no-inline-create.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(db): add migration 0002 to expand snapshots schema`
  - Files: `migrations/0002_expand_snapshots.sql`, `src/db/snapshots.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 2. Expand `src/db/snapshots.py` — New DB Query Functions (Story 2-2, 2-3, 2-5 foundation)

  **What to do**:
  - Add function `get_snapshot_metadata(snapshot_id: str, *, conn=None, db_path=None) -> dict | None` — fetch single snapshot row by ID
  - Add function `list_snapshots(ticker: str | None = None, *, archived: bool = False, conn=None, db_path=None) -> list[dict]` — list snapshots with optional ticker filter and archived filter, ordered by `created_at DESC`
  - Add function `mark_snapshots_archived(snapshot_ids: list[str], *, conn=None, db_path=None) -> int` — set `archived=1` and `archived_at=datetime.utcnow().isoformat()` for given IDs, return count updated
  - Add function `delete_snapshots(snapshot_ids: list[str], *, conn=None, db_path=None) -> int` — DELETE rows by ID, return count deleted
  - Add function `get_snapshot_by_path(snapshot_path: str, *, conn=None, db_path=None) -> dict | None` — fetch by path (for restore-verify)
  - Update `_upsert_snapshot_metadata()` to populate new columns: `snapshot_path`, `rows`, `checksum`, `job_id`, `size_bytes` from the metadata dict
  - Export ALL new public functions in `src/db/__init__.py`
  - Follow existing pattern: every function accepts optional `conn` and `db_path`, creates connection if none provided

  **Must NOT do**:
  - Do NOT use SQLAlchemy — raw `sqlite3` only
  - Do NOT add `retention_tier` logic — just `archived` boolean
  - Do NOT change `record_snapshot_metadata()` public signature — extend `_upsert_snapshot_metadata()` internally
  - Do NOT add `print()` or logging in DB functions (keep them pure data access)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple related functions in one module, requires understanding DB patterns and maintaining API consistency.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Task 1 (migration must exist first)
  - **Parallel Group**: Wave 1 (after Task 1)
  - **Blocks**: Tasks 3, 4, 7, 8, 11, 13
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `src/db/snapshots.py:1-114` — Full current module: `record_snapshot_metadata()`, `get_last_snapshot_payload()`, `_upsert_snapshot_metadata()` — follow exact pattern for connection handling, parameter style, docstrings
  - `src/db/prices.py:95-140` — `read_prices()` function showing optional `conn`/`db_path` pattern with fallback connection creation
  - `src/db/returns.py` — Another DB module following same pattern (for consistency reference)

  **API/Type References**:
  - `src/db/__init__.py:36-39` — Current snapshot exports to extend with new functions
  - `src/db/connection.py:18-35` — `connect()` and `_connect()` functions used to create connections when `conn` is None

  **WHY Each Reference Matters**:
  - `snapshots.py` shows the exact coding style: how `conn` fallback works, how SQL queries are structured, cursor usage
  - `prices.py:read_prices()` is the gold standard for optional conn/db_path pattern
  - `__init__.py` must export all new public functions or they won't be accessible via `from src.db import ...`

  **Acceptance Criteria**:
  - [ ] 5 new public functions exist in `src/db/snapshots.py`: `get_snapshot_metadata`, `list_snapshots`, `mark_snapshots_archived`, `delete_snapshots`, `get_snapshot_by_path`
  - [ ] All 5 exported in `src/db/__init__.py`
  - [ ] `_upsert_snapshot_metadata()` populates `snapshot_path`, `rows`, `checksum`, `job_id`, `size_bytes` from metadata dict
  - [ ] All functions follow `conn=None, db_path=None` optional parameter pattern

  **QA Scenarios**:

  ```
  Scenario: New functions are importable from src.db
    Tool: Bash
    Preconditions: Task 1 completed (migration exists)
    Steps:
      1. Run: poetry run python -c "
         from src.db import (
             get_snapshot_metadata,
             list_snapshots,
             mark_snapshots_archived,
             delete_snapshots,
             get_snapshot_by_path,
         )
         print('PASS: all functions importable')
         "
      2. Verify exit code is 0
    Expected Result: All 5 functions import successfully
    Failure Indicators: ImportError for any function
    Evidence: .sisyphus/evidence/task-2-imports.txt

  Scenario: CRUD operations work on in-memory DB
    Tool: Bash
    Preconditions: Migration applied
    Steps:
      1. Run: poetry run python -c "
         import sqlite3
         from src.db_migrator import apply_migrations
         from src.db.snapshots import (
             record_snapshot_metadata,
             get_snapshot_metadata,
             list_snapshots,
             mark_snapshots_archived,
             delete_snapshots,
         )
         conn = sqlite3.connect(':memory:')
         conn.executescript(open('migrations/0000_init_schema.sql').read())
         apply_migrations(conn)
         # Insert
         record_snapshot_metadata({
             'id': 'test-001',
             'ticker': 'PETR4',
             'created_at': '2026-01-01T00:00:00',
             'snapshot_path': '/tmp/test.csv',
             'rows': 100,
             'checksum': 'abc123',
             'size_bytes': 5000,
         }, conn=conn)
         # Read
         meta = get_snapshot_metadata('test-001', conn=conn)
         assert meta is not None, 'metadata not found'
         assert meta['checksum'] == 'abc123', f'wrong checksum: {meta}'
         # List
         items = list_snapshots('PETR4', conn=conn)
         assert len(items) == 1, f'expected 1, got {len(items)}'
         # Archive
         count = mark_snapshots_archived(['test-001'], conn=conn)
         assert count == 1, f'archived count: {count}'
         # Verify archived
         items = list_snapshots('PETR4', archived=False, conn=conn)
         assert len(items) == 0, 'should be 0 active after archive'
         items = list_snapshots('PETR4', archived=True, conn=conn)
         assert len(items) == 1, 'should be 1 archived'
         print('PASS: all CRUD operations work')
         "
      2. Verify exit code is 0
    Expected Result: Insert, read, list, archive all work correctly
    Failure Indicators: AssertionError, sqlite3.OperationalError
    Evidence: .sisyphus/evidence/task-2-crud-ops.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(db): add snapshot query functions for metadata, listing, archival`
  - Files: `src/db/snapshots.py`, `src/db/__init__.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 3. Implement `pipeline snapshot` CLI Command (Story 2-1)

  **What to do**:
  - Add `snapshot` command to `src/pipeline.py` Typer sub-app
  - Command signature: `snapshot(ticker: str, start: Optional[str] = None, end: Optional[str] = None, output_dir: Optional[str] = None)`
  - Flow:
    1. Normalize ticker via `_normalize_cli_ticker()` (existing helper at line 84-89)
    2. Read prices from DB via `db.read_prices(ticker, start, end)`
    3. If DataFrame is empty → `fb.error(f"Nenhum dado encontrado para {ticker}")`, `raise typer.Exit(code=1)`
    4. Determine output path: `output_dir / f"{ticker}_snapshot.csv"` (default `output_dir` = `SNAPSHOTS_DIR` from `src/paths.py`)
    5. Call `write_snapshot(df, out_path)` (existing function — returns SHA256 digest)
    6. Register metadata via `db.record_snapshot_metadata(...)` with: ticker, created_at, snapshot_path, rows, checksum (from `sha256_file()`), size_bytes
    7. Use `CliFeedback` for all output: `start()`, `info()`, `success()`
  - Handle edge cases:
    - Ticker not found in DB → exit code 1, error message
    - No data in date range → exit code 1, error message
    - Output directory doesn't exist → create it with `Path.mkdir(parents=True, exist_ok=True)`

  **Must NOT do**:
  - Do NOT use `print()` or `typer.echo()` — use `CliFeedback`
  - Do NOT fetch data from network — read from DB only
  - Do NOT modify `dados/data.db` — only READ from it
  - Do NOT add REST API endpoint — CLI only

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: CLI command with multiple flow steps, error handling, integration with DB + ETL + paths modules.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Tasks 1, 2
  - **Parallel Group**: Wave 1 (after Tasks 1, 2)
  - **Blocks**: Tasks 5, 7, 8
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `src/pipeline.py:27-45` — Typer sub-app creation pattern, existing commands structure
  - `src/pipeline.py:84-89` — `_normalize_cli_ticker()` helper, reuse for ticker validation
  - `src/pipeline.py:91-170` — `ingest` command: full CLI command pattern with CliFeedback, error handling, typer.Exit
  - `src/main.py:70` — `app.add_typer(pipeline_app, name="pipeline")` mounting pattern

  **API/Type References**:
  - `src/db/prices.py:95-101` — `read_prices(ticker, start, end, conn, db_path)` signature
  - `src/etl/snapshot.py:171` — `write_snapshot(df, out_path, *, set_permissions=False)` → returns SHA256
  - `src/utils/checksums.py:10-15` — `sha256_file(path)` → hex digest of file bytes
  - `src/paths.py:16` — `SNAPSHOTS_DIR` constant
  - `src/cli_feedback.py` — `CliFeedback(command_name)`, `.start()`, `.info()`, `.error()`, `.success()`

  **WHY Each Reference Matters**:
  - `pipeline.py:ingest` command is the exact pattern to copy: CliFeedback setup, ticker normalization, error handling with `typer.Exit(code=1)`, success messaging
  - `read_prices()` signature needed to call with correct params
  - `write_snapshot()` return value is the SHA256 digest — use `sha256_file()` instead for metadata registration (consistency decision)
  - `SNAPSHOTS_DIR` provides default output directory

  **Acceptance Criteria**:
  - [ ] Command `pipeline snapshot --ticker PETR4` generates CSV file in `snapshots/`
  - [ ] Command with `--start` and `--end` filters data range
  - [ ] Invalid ticker → exit code 1, error message via CliFeedback
  - [ ] Empty date range → exit code 1, error message
  - [ ] Metadata registered in `snapshots` table with checksum

  **QA Scenarios**:

  ```
  Scenario: Generate snapshot for valid ticker with data
    Tool: Bash
    Preconditions: dados/data.db exists with PETR4 price data
    Steps:
      1. Run: poetry run python -m src.main pipeline snapshot --ticker PETR4 --output-dir /tmp/test_snapshots
      2. Verify exit code is 0
      3. Verify file exists: ls /tmp/test_snapshots/PETR4_snapshot.csv
      4. Verify file has content: wc -l /tmp/test_snapshots/PETR4_snapshot.csv (should be > 1)
    Expected Result: CSV file created with price data, exit code 0
    Failure Indicators: Exit code != 0, file not created, empty file
    Evidence: .sisyphus/evidence/task-3-snapshot-valid-ticker.txt

  Scenario: Invalid ticker returns exit code 1
    Tool: Bash
    Preconditions: dados/data.db exists, no ticker ZZZZ99 in DB
    Steps:
      1. Run: poetry run python -m src.main pipeline snapshot --ticker ZZZZ99; echo "EXIT_CODE=$?"
      2. Verify output contains error message
      3. Verify EXIT_CODE=1
    Expected Result: Exit code 1, error message about no data found
    Failure Indicators: Exit code 0, or unhandled exception traceback
    Evidence: .sisyphus/evidence/task-3-snapshot-invalid-ticker.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(pipeline): add snapshot command to generate CSV from DB prices`
  - Files: `src/pipeline.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 4. Integrate Checksum Metadata Registration (Story 2-2)

  **What to do**:
  - Ensure `pipeline snapshot` command (Task 3) registers complete metadata after generating snapshot:
    - `id`: UUID or SHA256-based ID (existing `_upsert_snapshot_metadata` handles this)
    - `ticker`: normalized ticker string
    - `created_at`: ISO 8601 timestamp
    - `snapshot_path`: absolute path to generated CSV
    - `rows`: `len(df)` — number of data rows
    - `checksum`: `sha256_file(out_path)` — file-level checksum (NOT `snapshot_checksum()`)
    - `size_bytes`: `out_path.stat().st_size`
    - `payload`: JSON with additional metadata (date range, columns, etc.)
  - Verify idempotency: calling `pipeline snapshot` twice for same ticker produces INSERT OR REPLACE (no duplicate rows)
  - Verify `.checksum` sidecar file is written by `write_snapshot()` (already done by existing code)
  - This task is the "glue" ensuring Task 3's command properly populates all new columns from Task 1

  **Must NOT do**:
  - Do NOT use `snapshot_checksum(df)` for metadata — use `sha256_file(path)` (decision from Metis review)
  - Do NOT create new DB functions — use the ones from Task 2
  - Do NOT duplicate checksum logic — reuse `src/utils/checksums.py`

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Integration task connecting snapshot generation, DB metadata, and checksum — requires understanding all three systems.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Tasks 1, 2, 3
  - **Parallel Group**: Wave 1 (after Tasks 1, 2, 3)
  - **Blocks**: Tasks 6, 7, 8
  - **Blocked By**: Tasks 1, 2, 3

  **References**:

  **Pattern References**:
  - `src/db/snapshots.py:51-54` — `record_snapshot_metadata(metadata, conn, db_path)` public API
  - `src/db/snapshots.py:73-114` — `_upsert_snapshot_metadata()` internal: how metadata dict keys map to SQL columns, how `job_id` is auto-generated

  **API/Type References**:
  - `src/utils/checksums.py:10-15` — `sha256_file(path)` — THIS is the checksum to use for metadata
  - `src/etl/snapshot.py:171` — `write_snapshot()` return value (SHA256 from `snapshot_checksum()`) — NOT the one to use for metadata
  - `src/etl/snapshot.py:23` — `snapshot_checksum(df)` — uses `serialize_df_bytes()`, produces DIFFERENT hash than `sha256_file()` — do NOT confuse

  **WHY Each Reference Matters**:
  - `_upsert_snapshot_metadata()` determines how your metadata dict maps to DB columns — you must match the expected keys
  - `sha256_file()` vs `snapshot_checksum()` is a critical distinction — wrong one breaks CI validation in Story 2-4
  - `write_snapshot()` already writes `.checksum` sidecar — don't duplicate

  **Acceptance Criteria**:
  - [ ] After `pipeline snapshot --ticker PETR4`, query `snapshots` table shows row with non-null `checksum`, `rows`, `size_bytes`, `snapshot_path`
  - [ ] Checksum in DB matches `sha256_file()` of the generated CSV
  - [ ] Running command twice for same ticker → 1 row in DB (idempotent via INSERT OR REPLACE)
  - [ ] `.checksum` sidecar file exists next to generated CSV

  **QA Scenarios**:

  ```
  Scenario: Metadata fully populated after snapshot generation
    Tool: Bash
    Preconditions: Tasks 1-3 completed, dados/data.db has PETR4 data
    Steps:
      1. Run: poetry run python -m src.main pipeline snapshot --ticker PETR4 --output-dir /tmp/test_snap
      2. Run: poetry run python -c "
         import sqlite3
         conn = sqlite3.connect('dados/data.db')
         conn.row_factory = sqlite3.Row
         rows = conn.execute('SELECT * FROM snapshots WHERE ticker = ?', ('PETR4',)).fetchall()
         assert len(rows) >= 1, f'expected >=1 rows, got {len(rows)}'
         row = dict(rows[-1])
         print('ROW:', row)
         assert row['checksum'] is not None, 'checksum is null'
         assert row['rows'] is not None, 'rows is null'
         assert row['size_bytes'] is not None, 'size_bytes is null'
         assert row['snapshot_path'] is not None, 'snapshot_path is null'
         print('PASS: metadata fully populated')
         "
    Expected Result: All metadata fields populated in DB
    Failure Indicators: AssertionError for any null field
    Evidence: .sisyphus/evidence/task-4-metadata-populated.txt

  Scenario: Checksum matches sha256_file result
    Tool: Bash
    Preconditions: Snapshot generated at known path
    Steps:
      1. Run: poetry run python -c "
         import sqlite3
         from src.utils.checksums import sha256_file
         conn = sqlite3.connect('dados/data.db')
         conn.row_factory = sqlite3.Row
         row = dict(conn.execute(
             'SELECT * FROM snapshots WHERE ticker = ? ORDER BY created_at DESC LIMIT 1',
             ('PETR4',)
         ).fetchone())
         file_checksum = sha256_file(row['snapshot_path'])
         db_checksum = row['checksum']
         assert file_checksum == db_checksum, f'mismatch: file={file_checksum}, db={db_checksum}'
         print(f'PASS: checksums match ({db_checksum[:16]}...)')
         "
    Expected Result: File checksum equals DB checksum
    Failure Indicators: AssertionError with mismatched values
    Evidence: .sisyphus/evidence/task-4-checksum-match.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(snapshots): integrate sha256 checksum metadata registration`
  - Files: `src/pipeline.py`, `src/db/snapshots.py` (if _upsert changes needed)
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 5. Tests for Story 2-1 — Snapshot Generation (`pipeline snapshot`)

  **What to do**:
  - Create `tests/test_pipeline_snapshot.py` with pytest tests
  - Tests to write:
    1. `test_snapshot_generates_csv_file` — valid ticker → CSV file created in output dir
    2. `test_snapshot_csv_has_correct_columns` — CSV columns match `read_prices()` output columns
    3. `test_snapshot_with_date_range` — `--start` and `--end` filter data correctly
    4. `test_snapshot_invalid_ticker_exit_code_1` — unknown ticker → `SystemExit(1)`
    5. `test_snapshot_empty_date_range_exit_code_1` — valid ticker but no data in range → exit code 1
    6. `test_snapshot_creates_output_dir` — if output dir doesn't exist, it's created
    7. `test_snapshot_default_output_dir` — without `--output-dir`, uses `SNAPSHOTS_DIR`
  - Use `CliRunner` from Typer for CLI invocation testing
  - Use `sample_db` fixture or `create_prices_db_from_csv()` for test DB with known data
  - Use `tmp_path` fixture for output directory

  **Must NOT do**:
  - Do NOT mock the DB layer — use in-memory SQLite with real data
  - Do NOT test checksum registration here — that's Task 6 (Story 2-2 tests)
  - Do NOT use `snapshot_dir` session fixture — use `tmp_path` (per-test isolation)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple test cases requiring understanding of CLI testing patterns, DB fixtures, and file assertions.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES — can run parallel with Task 6
  - **Parallel Group**: Wave 1 (after Task 3)
  - **Blocks**: None
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `tests/test_cli.py` — If exists, CLI testing patterns with CliRunner
  - `tests/conftest.py:14-30` — `sample_db` fixture: creates in-memory SQLite with sample data from CSV
  - `tests/fixture_utils.py:1-30` — `create_prices_db_from_csv()` for creating test DBs from fixture CSVs

  **Test References**:
  - `tests/test_snapshot.py` — Existing snapshot tests for `write_snapshot()` patterns
  - `tests/conftest.py:33-40` — `snapshot_dir` fixture (session-scoped — DON'T use for per-test isolation)

  **External References**:
  - Typer testing docs: `from typer.testing import CliRunner`

  **WHY Each Reference Matters**:
  - `sample_db` fixture provides pre-populated in-memory DB — reuse instead of creating custom fixtures
  - `fixture_utils.py` shows how to create DBs from CSV — reuse if sample_db doesn't suffice
  - Existing test files show assertion patterns, import style, and pytest conventions used in project

  **Acceptance Criteria**:
  - [ ] `tests/test_pipeline_snapshot.py` exists with ≥ 7 test functions
  - [ ] `poetry run pytest tests/test_pipeline_snapshot.py -v` → all tests pass

  **QA Scenarios**:

  ```
  Scenario: All Story 2-1 tests pass
    Tool: Bash
    Preconditions: Tasks 1-3 completed
    Steps:
      1. Run: poetry run pytest tests/test_pipeline_snapshot.py -v
      2. Verify output shows all tests PASSED
      3. Verify exit code is 0
    Expected Result: ≥ 7 tests pass, 0 failures
    Failure Indicators: Any FAILED test, exit code != 0
    Evidence: .sisyphus/evidence/task-5-tests-story-2-1.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `test(snapshots): add tests for pipeline snapshot command (Story 2-1)`
  - Files: `tests/test_pipeline_snapshot.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 6. Tests for Story 2-2 — Checksum Metadata Registration

  **What to do**:
  - Create `tests/test_snapshot_metadata.py` with pytest tests
  - Tests to write:
    1. `test_metadata_registered_after_snapshot` — after `pipeline snapshot`, DB has row with all fields populated
    2. `test_checksum_matches_sha256_file` — `checksum` in DB equals `sha256_file()` of generated CSV
    3. `test_checksum_sidecar_written` — `.checksum` sidecar file exists next to CSV
    4. `test_metadata_idempotent_on_rerun` — running `pipeline snapshot` twice → single row in DB (INSERT OR REPLACE)
    5. `test_metadata_rows_count_matches_df` — `rows` field in DB matches `len(df)`
    6. `test_metadata_size_bytes_matches_file` — `size_bytes` in DB matches `os.path.getsize()` of CSV
  - Use in-memory SQLite with migration applied
  - Test both the DB functions directly AND via CLI command

  **Must NOT do**:
  - Do NOT test CLI flow here — focus on metadata correctness
  - Do NOT compare `snapshot_checksum()` with `sha256_file()` — they are DIFFERENT by design

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Data integrity tests requiring precise assertions on checksums and metadata fields.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES — can run parallel with Task 5
  - **Parallel Group**: Wave 1 (after Task 4)
  - **Blocks**: None
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `src/db/snapshots.py` — Functions being tested
  - `src/utils/checksums.py:10-15` — `sha256_file()` for verification assertions
  - `tests/test_snapshot.py` — Existing snapshot test patterns

  **WHY Each Reference Matters**:
  - Need to know exact function signatures to write test calls
  - `sha256_file()` is the reference implementation for checksum verification
  - Existing test patterns show project testing conventions

  **Acceptance Criteria**:
  - [ ] `tests/test_snapshot_metadata.py` exists with ≥ 6 test functions
  - [ ] `poetry run pytest tests/test_snapshot_metadata.py -v` → all tests pass

  **QA Scenarios**:

  ```
  Scenario: All Story 2-2 tests pass
    Tool: Bash
    Preconditions: Tasks 1-4 completed
    Steps:
      1. Run: poetry run pytest tests/test_snapshot_metadata.py -v
      2. Verify output shows all tests PASSED
      3. Verify exit code is 0
    Expected Result: ≥ 6 tests pass, 0 failures
    Failure Indicators: Any FAILED test, exit code != 0
    Evidence: .sisyphus/evidence/task-6-tests-story-2-2.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `test(snapshots): add tests for checksum metadata registration (Story 2-2)`
  - Files: `tests/test_snapshot_metadata.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 7. Implement `snapshots export` CLI Command (Story 2-3)

  **What to do**:
  - Create `src/snapshot_cli.py` as new Typer sub-app: `app = typer.Typer()`
  - Add `export` command: `export(ticker: str, format: str = "csv", start: Optional[str] = None, end: Optional[str] = None, output: Optional[str] = None)`
  - Mount in `src/main.py`: `app.add_typer(snapshot_cli_app, name="snapshots")`
  - Flow for CSV format:
    1. Query `list_snapshots(ticker)` from DB to find latest snapshot
    2. If `--output` specified → copy snapshot file to output path
    3. If no `--output` → write CSV content to stdout
    4. Include metadata header comment (ticker, date range, checksum, rows)
  - Flow for JSON format:
    1. Read snapshot CSV into DataFrame
    2. Convert to JSON with `records` orientation
    3. Include metadata wrapper: `{"ticker": ..., "checksum": ..., "rows": ..., "data": [...]}`
    4. If `--output` → write to file; else → write to stdout
  - Use `CliFeedback` for progress/status messages (to stderr, NOT stdout — stdout is for data)
  - Handle edge cases: no snapshots found → exit code 1, invalid format → exit code 1

  **Must NOT do**:
  - Do NOT create REST API endpoints — CLI only
  - Do NOT create `src/cli/` directory — keep flat in `src/`
  - Do NOT mix status messages with data output on stdout
  - Do NOT use `print()` directly for status — use `CliFeedback` (which goes to stderr)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: New CLI module with dual format output, stdout/stderr separation, metadata integration, and Typer sub-app mounting.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES — parallel with Task 8
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 2, 3, 4

  **References**:

  **Pattern References**:
  - `src/pipeline.py:27-45` — Typer sub-app creation pattern to follow
  - `src/main.py:70` — `app.add_typer()` mounting pattern — add similar line for snapshots
  - `src/pipeline.py:91-170` — `ingest` command for CliFeedback usage pattern
  - `src/ingest_cli.py` — Another separate CLI module example

  **API/Type References**:
  - `src/db/snapshots.py` — `list_snapshots(ticker, archived=False)`, `get_snapshot_metadata(id)` — for querying snapshot data
  - `src/paths.py:16` — `SNAPSHOTS_DIR` for locating snapshot files
  - `src/cli_feedback.py` — CliFeedback API: route status to stderr via `file=sys.stderr` or Typer's stderr option

  **WHY Each Reference Matters**:
  - `pipeline.py` sub-app pattern is the exact model to follow for `snapshot_cli.py`
  - `main.py:70` shows where and how to mount new sub-apps
  - `ingest_cli.py` shows a standalone CLI module — same pattern for `snapshot_cli.py`
  - `list_snapshots()` from Task 2 provides the data query layer

  **Acceptance Criteria**:
  - [ ] `src/snapshot_cli.py` exists with `export` command
  - [ ] Mounted in `src/main.py` as `snapshots` sub-app
  - [ ] `snapshots export --ticker PETR4 --format csv` → CSV data to stdout
  - [ ] `snapshots export --ticker PETR4 --format json` → JSON with metadata wrapper to stdout
  - [ ] `snapshots export --ticker PETR4 --format csv --output /tmp/out.csv` → file written
  - [ ] Invalid ticker → exit code 1
  - [ ] Invalid format → exit code 1

  **QA Scenarios**:

  ```
  Scenario: Export CSV to stdout
    Tool: Bash
    Preconditions: PETR4 snapshot exists in DB and on disk (from Task 3)
    Steps:
      1. Run: poetry run python -m src.main snapshots export --ticker PETR4 --format csv > /tmp/export_test.csv
      2. Verify exit code is 0
      3. Verify /tmp/export_test.csv has content: wc -l /tmp/export_test.csv (should be > 1)
      4. Verify CSV has valid headers (first non-comment line)
    Expected Result: CSV data written to stdout, captured in file
    Failure Indicators: Exit code != 0, empty file, no CSV headers
    Evidence: .sisyphus/evidence/task-7-export-csv-stdout.txt

  Scenario: Export JSON to stdout
    Tool: Bash
    Preconditions: PETR4 snapshot exists
    Steps:
      1. Run: poetry run python -m src.main snapshots export --ticker PETR4 --format json > /tmp/export_test.json
      2. Verify exit code is 0
      3. Run: poetry run python -c "
         import json
         data = json.load(open('/tmp/export_test.json'))
         assert 'ticker' in data, 'missing ticker key'
         assert 'data' in data, 'missing data key'
         assert isinstance(data['data'], list), 'data not a list'
         assert len(data['data']) > 0, 'empty data array'
         print(f'PASS: JSON valid, {len(data[\"data\"])} records')
         "
    Expected Result: Valid JSON with ticker, checksum, rows, data fields
    Failure Indicators: json.JSONDecodeError, missing keys
    Evidence: .sisyphus/evidence/task-7-export-json-stdout.txt

  Scenario: No snapshots found for ticker returns exit code 1
    Tool: Bash
    Preconditions: No snapshot for ZZZZ99
    Steps:
      1. Run: poetry run python -m src.main snapshots export --ticker ZZZZ99 --format csv; echo "EXIT=$?"
      2. Verify EXIT=1
    Expected Result: Exit code 1, error message
    Failure Indicators: Exit code 0, or unhandled exception
    Evidence: .sisyphus/evidence/task-7-export-no-snapshot.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(cli): add snapshots export command with CSV/JSON formats (Story 2-3)`
  - Files: `src/snapshot_cli.py`, `src/main.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 8. Implement CI Checksum Validation Script (Story 2-4)

  **What to do**:
  - Create `scripts/ci_validate_checksums.py` — standalone script (NOT a CLI command)
  - Flow:
    1. Connect to DB (`dados/data.db`)
    2. Query all non-archived snapshots from `snapshots` table
    3. For each snapshot with a `snapshot_path` and `checksum`:
       a. Verify file exists at `snapshot_path`
       b. Compute `sha256_file(snapshot_path)`
       c. Compare with stored `checksum`
    4. Report results: total checked, passed, failed, missing files
    5. Exit code 0 if all pass, exit code 1 if any fail
  - Output format: structured text to stdout with clear PASS/FAIL per snapshot
  - Handle edge cases: no snapshots in DB → exit 0 (nothing to validate), file missing → FAIL

  **Must NOT do**:
  - Do NOT use `snapshot_checksum()` — use `sha256_file()` (consistency with Story 2-2)
  - Do NOT modify DB — read-only validation
  - Do NOT add as Typer command — standalone script for CI
  - Do NOT add REST endpoint

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Self-contained script with clear inputs/outputs, DB read + file validation.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES — parallel with Task 7
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 3, 4

  **References**:

  **Pattern References**:
  - `scripts/validate_snapshots.py` — Existing validation script pattern to follow
  - `scripts/generate_ci_snapshot.py` — Another CI script example showing structure, imports, exit codes
  - `scripts/ci_orchestrator.py` — CI orchestration script showing how scripts report results

  **API/Type References**:
  - `src/db/snapshots.py` — `list_snapshots()` for querying all snapshots
  - `src/utils/checksums.py:10-15` — `sha256_file(path)` for computing file checksum
  - `src/db/connection.py:18-35` — `connect()` for DB connection

  **WHY Each Reference Matters**:
  - `validate_snapshots.py` is the closest existing pattern — same domain (snapshot validation)
  - `sha256_file()` is the exact function to use — must match what Story 2-2 stores
  - `list_snapshots()` from Task 2 provides snapshot enumeration

  **Acceptance Criteria**:
  - [ ] `scripts/ci_validate_checksums.py` exists
  - [ ] Running with valid checksums → exit code 0, summary showing all PASS
  - [ ] Running with tampered file → exit code 1, shows which file failed
  - [ ] Running with no snapshots → exit code 0
  - [ ] Running with missing file → exit code 1, shows missing path

  **QA Scenarios**:

  ```
  Scenario: Valid checksums pass validation
    Tool: Bash
    Preconditions: PETR4 snapshot exists with valid checksum in DB
    Steps:
      1. Run: poetry run python scripts/ci_validate_checksums.py
      2. Verify exit code is 0
      3. Verify output contains "PASS" for PETR4
    Expected Result: Exit code 0, all snapshots pass
    Failure Indicators: Exit code != 0, FAIL in output
    Evidence: .sisyphus/evidence/task-8-ci-valid-checksums.txt

  Scenario: Tampered file fails validation
    Tool: Bash
    Preconditions: PETR4 snapshot exists
    Steps:
      1. Find snapshot path from DB
      2. Append garbage to a copy of the file to simulate tampering
      3. Update DB snapshot_path to point at tampered file
      4. Run: poetry run python scripts/ci_validate_checksums.py; echo "EXIT=$?"
      5. Verify EXIT=1
      6. Verify output shows FAIL for the tampered snapshot
    Expected Result: Exit code 1, clear failure report
    Failure Indicators: Exit code 0 despite tampered file
    Evidence: .sisyphus/evidence/task-8-ci-tampered-file.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(ci): add checksum validation script for snapshot integrity (Story 2-4)`
  - Files: `scripts/ci_validate_checksums.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 9. Tests for Story 2-3 — Snapshots Export CLI

  **What to do**:
  - Create `tests/test_snapshots_export.py` with pytest tests
  - Tests to write:
    1. `test_export_csv_to_stdout` — CSV data on stdout, status on stderr
    2. `test_export_json_to_stdout` — valid JSON with metadata wrapper, `records` orientation
    3. `test_export_csv_to_file` — `--output` flag writes file, file has content
    4. `test_export_json_to_file` — `--output` flag writes JSON file
    5. `test_export_no_snapshot_exit_1` — unknown ticker → exit 1
    6. `test_export_json_has_metadata_fields` — JSON contains `ticker`, `checksum`, `rows`, `data`
    7. `test_snapshots_subapp_mounted` — `snapshots export --help` works from main app
  - Use CliRunner for CLI testing, tmp_path for output files
  - Setup: create a snapshot via `write_snapshot()` + `record_snapshot_metadata()` in fixture

  **Must NOT do**:
  - Do NOT test DB functions directly — focus on CLI behavior
  - Do NOT use `snapshot_dir` session fixture — use per-test `tmp_path`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: CLI testing with stdout/stderr capture, JSON validation, file output assertions.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES — parallel with Task 10
  - **Parallel Group**: Wave 2 (after Task 7)
  - **Blocks**: None
  - **Blocked By**: Task 7

  **References**:

  **Pattern References**:
  - `tests/test_pipeline_snapshot.py` — Testing patterns from Task 5 (reuse fixture strategy)
  - `tests/conftest.py` — Shared fixtures

  **WHY Each Reference Matters**:
  - Task 5's tests show the CliRunner + DB fixture pattern to follow consistently

  **Acceptance Criteria**:
  - [ ] `tests/test_snapshots_export.py` exists with ≥ 7 test functions
  - [ ] `poetry run pytest tests/test_snapshots_export.py -v` → all pass

  **QA Scenarios**:

  ```
  Scenario: All Story 2-3 tests pass
    Tool: Bash
    Preconditions: Tasks 1-4, 7 completed
    Steps:
      1. Run: poetry run pytest tests/test_snapshots_export.py -v
      2. Verify all PASSED, exit code 0
    Expected Result: ≥ 7 tests pass, 0 failures
    Failure Indicators: Any FAILED test
    Evidence: .sisyphus/evidence/task-9-tests-story-2-3.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `test(snapshots): add tests for snapshots export CLI (Story 2-3)`
  - Files: `tests/test_snapshots_export.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 10. Tests for Story 2-4 — CI Checksum Validation

  **What to do**:
  - Create `tests/test_ci_validate_checksums.py` with pytest tests
  - Tests to write:
    1. `test_valid_checksums_pass` — all files match checksums → exit 0
    2. `test_tampered_file_fails` — modified file → exit 1
    3. `test_missing_file_fails` — file at snapshot_path doesn't exist → exit 1
    4. `test_no_snapshots_passes` — empty DB → exit 0
    5. `test_output_format_shows_results` — stdout contains PASS/FAIL per snapshot
  - Import and call the script's main function directly (or use subprocess)
  - Setup: create snapshot files + DB metadata in tmp dirs

  **Must NOT do**:
  - Do NOT test against `dados/data.db` — use isolated test DB

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Script testing with file manipulation, DB setup, and exit code assertions.
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES — parallel with Task 9
  - **Parallel Group**: Wave 2 (after Task 8)
  - **Blocks**: None
  - **Blocked By**: Task 8

  **References**:

  **Pattern References**:
  - `scripts/ci_validate_checksums.py` — The script being tested (from Task 8)
  - `tests/test_snapshot.py` — Existing snapshot test patterns

  **Acceptance Criteria**:
  - [ ] `tests/test_ci_validate_checksums.py` exists with ≥ 5 test functions
  - [ ] `poetry run pytest tests/test_ci_validate_checksums.py -v` → all pass

  **QA Scenarios**:

  ```
  Scenario: All Story 2-4 tests pass
    Tool: Bash
    Preconditions: Task 8 completed
    Steps:
      1. Run: poetry run pytest tests/test_ci_validate_checksums.py -v
      2. Verify all PASSED, exit code 0
    Expected Result: ≥ 5 tests pass, 0 failures
    Failure Indicators: Any FAILED test
    Evidence: .sisyphus/evidence/task-10-tests-story-2-4.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `test(ci): add tests for CI checksum validation script (Story 2-4)`
  - Files: `tests/test_ci_validate_checksums.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

### Wave 3 — Stories 2-5 (Retention/Purge) e 2-6 (Restore-Verify)

- [x] 11. Implementar módulo de retenção e comando `snapshots purge` (Story 2-5)

  **What to do**:
  - Criar `src/retention.py` com a lógica de retenção:
    - `get_retention_days() -> int`: lê `SNAPSHOT_RETENTION_DAYS` env var (default `90`), retorna int
    - `find_purge_candidates(conn, older_than_days: int) -> list[dict]`: query na tabela `snapshots` por `created_at < now - older_than_days` AND `archived = 0`, retorna lista de dicts com `id, path, ticker, created_at, size_bytes, checksum`
    - `archive_snapshots(conn, snapshot_ids: list[int], archive_dir: Path) -> list[dict]`: para cada id, copia arquivo para `archive_dir`, verifica SHA256 do arquivo copiado vs metadado, marca `archived=1` e `archived_at=datetime.utcnow().isoformat()` na DB, retorna lista de resultados `{id, path, archived_path, checksum_ok}`
    - `delete_snapshots(conn, snapshot_ids: list[int]) -> list[dict]`: para cada id, deleta arquivo do FS (com `contextlib.suppress(OSError)`), deleta `.checksum` sidecar se existir, chama `delete_snapshots()` de `src/db/snapshots.py` para remover da DB, retorna lista de resultados `{id, path, deleted}`
  - Adicionar comando `purge` ao sub-app `snapshots_app` em `src/snapshot_cli.py`:
    - Flag `--older-than` (int, default lê de `get_retention_days()`)
    - Flag `--dry-run` (bool, default `False`) — lista candidatos sem modificar
    - Flag `--confirm` (bool, default `False`) — executa exclusão real
    - Flag `--archive-dir` (Path, opcional) — se fornecido, arquiva ao invés de deletar
    - Sem `--confirm` e sem `--dry-run`: mostrar candidatos e mensagem "use --confirm para executar"
    - Com `--dry-run`: listar candidatos via `CliFeedback`, exit 0
    - Com `--confirm` e `--archive-dir`: chamar `archive_snapshots()`, exibir resumo
    - Com `--confirm` sem `--archive-dir`: chamar `delete_snapshots()`, exibir resumo
    - Validação: se `--dry-run` e `--confirm` juntos, `CliFeedback.error()` + `raise typer.Exit(code=1)`
  - Usar `CliFeedback` para toda saída (nunca `print()`/`typer.echo()`)
  - Respeitar line-length 88 chars

  **Must NOT do**:
  - NÃO implementar `keep_monthly`, `keep_yearly`, `min_free_space_mb` (simplificado para `SNAPSHOT_RETENTION_DAYS` apenas)
  - NÃO implementar `retention_tier` na DB (usar apenas `archived` boolean)
  - NÃO verificar `os.geteuid()` ou permissões de usuário (fora de escopo)
  - NÃO criar `src/cli/` directory — manter flat em `src/`
  - NÃO usar `print()`/`typer.echo()` diretamente

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Lógica de retenção com múltiplas operações coordenadas (DB + FS + CLI), edge cases de arquivamento, validação de checksum
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Sem UI, apenas CLI
    - `git-master`: Sem operações git

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential within wave — depends on Wave 1+2 DB schema)
  - **Blocks**: [Task 12]
  - **Blocked By**: [Tasks 1, 2] (schema migration + DB functions needed)

  **References**:

  **Pattern References**:
  - `src/etl/snapshot.py:96-168` — `_prune_old_snapshots()` existente, padrão de pruning com glob + sort + unlink, referência para como tratar arquivos com `contextlib.suppress(OSError)`
  - `src/snapshot_cli.py` (Task 7) — sub-app Typer onde o comando `purge` será adicionado, seguir padrão de flags e callback
  - `src/pipeline.py:1-60` — padrão de comando CLI com Typer: callback, flags, `CliFeedback`, exit codes

  **API/Type References**:
  - `src/db/snapshots.py` (Task 2) — `list_snapshots()`, `mark_snapshots_archived()`, `delete_snapshots()` — funções DB disponíveis após Wave 1
  - `src/utils/checksums.py:sha256_file()` — usar para verificar integridade pré-delete/archive
  - `src/cli_feedback.py:CliFeedback` — usar `.info()`, `.success()`, `.warning()`, `.error()`, `.table()` para output

  **External References**:
  - Story spec: `docs/implementation-artifacts/2-5-politica-de-retencao-e-purge-de-snapshots.md`

  **WHY Each Reference Matters**:
  - `_prune_old_snapshots()` mostra o padrão existente de limpeza de arquivos com glob + suppress(OSError), deve ser seguido para consistência
  - `src/db/snapshots.py` provê as funções DB que Task 11 chama — NÃO reimplementar queries
  - `sha256_file()` é o checksum canônico do projeto para arquivos — usar em vez de `snapshot_checksum()`

  **Acceptance Criteria**:
  - [ ] `src/retention.py` existe com 4 funções: `get_retention_days`, `find_purge_candidates`, `archive_snapshots`, `delete_snapshots`
  - [ ] Comando `purge` acessível via `poetry run python -m src.main snapshots purge --help`
  - [ ] `--dry-run` lista candidatos sem modificar DB ou FS
  - [ ] `--confirm` deleta arquivos e remove da DB
  - [ ] `--confirm --archive-dir snapshots/archive/` copia, verifica checksum, marca `archived=1`
  - [ ] `--dry-run --confirm` juntos retorna erro (exit 1)
  - [ ] `CliFeedback` usado para toda saída

  **QA Scenarios**:

  ```
  Scenario: Purge dry-run lists candidates without modifying state
    Tool: Bash
    Preconditions: DB com ≥ 2 snapshots com created_at > 1 dia atrás; arquivos existem no FS
    Steps:
      1. Run: poetry run python -m src.main snapshots purge --older-than 0 --dry-run
      2. Capture stdout — deve listar snapshots candidatos
      3. Verify DB: snapshots ainda existem (SELECT COUNT(*) FROM snapshots WHERE archived=0)
      4. Verify FS: arquivos ainda existem no diretório
    Expected Result: Lista de candidatos exibida, exit code 0, nenhuma modificação
    Failure Indicators: Arquivo deletado, registro removido da DB, exit code ≠ 0
    Evidence: .sisyphus/evidence/task-11-purge-dryrun.txt

  Scenario: Purge confirm deletes files and DB records
    Tool: Bash
    Preconditions: DB com snapshot antigo; arquivo existe no FS
    Steps:
      1. Run: poetry run python -m src.main snapshots purge --older-than 0 --confirm
      2. Verify: arquivo removido do FS
      3. Verify DB: registro removido (SELECT COUNT(*) FROM snapshots WHERE path='<path>')
    Expected Result: Arquivo e registro removidos, exit code 0
    Failure Indicators: Arquivo ainda existe, registro ainda na DB
    Evidence: .sisyphus/evidence/task-11-purge-confirm.txt

  Scenario: Purge with --archive-dir copies before marking archived
    Tool: Bash
    Preconditions: DB com snapshot; arquivo existe no FS
    Steps:
      1. Run: poetry run python -m src.main snapshots purge --older-than 0 --confirm --archive-dir /tmp/test-archive
      2. Verify: arquivo copiado para /tmp/test-archive/
      3. Verify: checksum do arquivo copiado == checksum original (sha256sum)
      4. Verify DB: archived=1, archived_at IS NOT NULL
    Expected Result: Arquivo copiado e verificado, DB atualizada, exit code 0
    Failure Indicators: Arquivo não copiado, checksum mismatch, archived=0
    Evidence: .sisyphus/evidence/task-11-purge-archive.txt

  Scenario: Conflicting --dry-run and --confirm flags produce error
    Tool: Bash
    Steps:
      1. Run: poetry run python -m src.main snapshots purge --dry-run --confirm
      2. Capture stderr
    Expected Result: Mensagem de erro via CliFeedback, exit code 1
    Failure Indicators: Exit code 0, nenhuma mensagem de erro
    Evidence: .sisyphus/evidence/task-11-purge-conflict-flags.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(retention): add retention policy and snapshots purge command (Story 2-5)`
  - Files: `src/retention.py`, `src/snapshot_cli.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 12. Testes para Story 2-5 — Retenção e Purge

  **What to do**:
  - Criar `tests/test_retention_purge.py` com os seguintes testes:
    1. `test_get_retention_days_default` — sem env var, retorna 90
    2. `test_get_retention_days_custom` — com `SNAPSHOT_RETENTION_DAYS=30`, retorna 30
    3. `test_get_retention_days_invalid` — com valor não-numérico, retorna default 90 (ou levanta ValueError — seguir padrão de `get_snapshot_keep_latest`)
    4. `test_find_purge_candidates_returns_old_snapshots` — inserir snapshots com `created_at` antigo e recente, verificar que apenas antigos retornam
    5. `test_find_purge_candidates_excludes_archived` — inserir snapshot com `archived=1`, verificar que NÃO retorna
    6. `test_archive_snapshots_copies_and_marks` — criar arquivo snapshot em `tmp_path`, chamar `archive_snapshots()`, verificar: cópia existe em archive_dir, checksum bate, DB `archived=1`
    7. `test_archive_snapshots_checksum_mismatch` — simular checksum diferente (truncar arquivo copiado), verificar que não marca `archived=1` e reporta erro
    8. `test_delete_snapshots_removes_files_and_db` — criar arquivo + registro DB, chamar `delete_snapshots()`, verificar: arquivo removido, registro removido
    9. `test_delete_snapshots_missing_file_no_crash` — registro na DB mas arquivo ausente no FS, verificar que não levanta exceção (suppress OSError)
    10. `test_purge_dryrun_no_side_effects` — invocar comando `purge --dry-run` via `CliRunner`, verificar que DB e FS não mudaram
  - Fixtures: usar `sample_db` + `tmp_path`, inserir registros na tabela `snapshots` com `created_at` manipulado, criar arquivos CSV temporários
  - Usar `monkeypatch` para env vars (`SNAPSHOT_RETENTION_DAYS`)

  **Must NOT do**:
  - NÃO testar `keep_monthly`/`keep_yearly`/`min_free_space_mb` (não implementados)
  - NÃO criar fixtures que dependam de rede
  - NÃO usar mocks excessivos — preferir `tmp_path` + SQLite in-memory

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Testes com múltiplas fixtures e cenários, mas lógica direta
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 11)
  - **Parallel Group**: Wave 3 (after Task 11)
  - **Blocks**: []
  - **Blocked By**: [Task 11]

  **References**:

  **Pattern References**:
  - `tests/test_pipeline_snapshot.py` (Task 5) — padrão de teste com `sample_db`, `tmp_path`, inserção de dados, invocação CLI via `CliRunner`
  - `tests/conftest.py` — fixtures `sample_db`, `snapshot_dir`, padrão de DB in-memory

  **API/Type References**:
  - `src/retention.py` (Task 11) — funções a testar: `get_retention_days`, `find_purge_candidates`, `archive_snapshots`, `delete_snapshots`
  - `src/snapshot_cli.py` (Task 7+11) — comando `purge` para teste via `CliRunner`

  **Test References**:
  - `tests/test_snapshot_metadata.py` (Task 6) — padrão de como testar funções DB de snapshots
  - `src/ingest/config.py:75` — `get_snapshot_keep_latest()` padrão de parsing env var com fallback

  **WHY Each Reference Matters**:
  - `tests/test_pipeline_snapshot.py` mostra como montar cenário end-to-end com DB + FS + CLI
  - `tests/conftest.py` provê as fixtures reusáveis — NÃO recriar
  - `src/ingest/config.py` mostra padrão de env var parsing com fallback — seguir para `get_retention_days()`

  **Acceptance Criteria**:
  - [ ] `tests/test_retention_purge.py` existe com ≥ 10 test functions
  - [ ] `poetry run pytest tests/test_retention_purge.py -v` → all pass
  - [ ] Cobertura: dry-run, confirm, archive, delete, env var parsing, edge cases

  **QA Scenarios**:

  ```
  Scenario: All Story 2-5 tests pass
    Tool: Bash
    Preconditions: Task 11 completed
    Steps:
      1. Run: poetry run pytest tests/test_retention_purge.py -v
      2. Verify all PASSED, exit code 0
    Expected Result: ≥ 10 tests pass, 0 failures
    Failure Indicators: Any FAILED test
    Evidence: .sisyphus/evidence/task-12-tests-story-2-5.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `test(retention): add tests for retention policy and purge command (Story 2-5)`
  - Files: `tests/test_retention_purge.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 13. Implementar comando `pipeline restore-verify` (Story 2-6)

  **What to do**:
  - Adicionar comando `restore-verify` ao sub-app `pipeline_app` em `src/pipeline.py`:
    - Flag `--snapshot-path` (Path, required) — caminho para CSV de snapshot
    - Flag `--temp-db` (Path, opcional, default `:memory:`) — para inspeção local
  - Lógica do comando:
    1. Verificar que `--snapshot-path` existe, senão `CliFeedback.error()` + exit 2
    2. Calcular SHA256 do arquivo via `sha256_file(snapshot_path)`
    3. Buscar metadado na DB via `get_snapshot_by_path(conn, snapshot_path)` (Task 2)
    4. Se metadado existe, comparar checksum calculado vs `checksum` da DB
    5. Criar DB temporário (`:memory:` ou `--temp-db` path)
    6. Ler CSV com `pd.read_csv(snapshot_path)`, inserir no DB temporário usando `INSERT INTO prices (...) VALUES (...)` para cada row (batch insert)
    7. Executar verificações de integridade:
       - `row_count`: COUNT(*) no DB temporário == len(df)
       - `columns_present`: todas as colunas canônicas presentes no CSV (`ticker`, `date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`)
       - `checksum_match`: SHA256 do arquivo vs metadado (se disponível)
       - `sample_row_check`: primeira e última row do CSV existem no DB temporário
    8. Gerar relatório estruturado JSON com:
       - `job_id`: UUID gerado
       - `snapshot_path`: path do arquivo
       - `timestamp`: datetime UTC
       - `checks`: dict com cada verificação e resultado (pass/fail)
       - `rows_restored`: int
       - `overall_result`: "PASS" | "WARN" | "FAIL"
    9. Exit codes: 0=PASS (tudo ok), 1=WARN (checksum mismatch mas rows ok), 2=FAIL (arquivo não existe, colunas ausentes, rows não inseridas)
    10. Imprimir relatório JSON via `CliFeedback.info()` (pretty-printed)
  - Usar `CliFeedback` para toda saída
  - Respeitar line-length 88 chars

  **Must NOT do**:
  - NÃO criar módulo separado `src/snapshots/manager.py` — lógica inline no comando ou helper function no mesmo arquivo
  - NÃO usar SQLAlchemy
  - NÃO modificar `dados/data.db` — DB temporário apenas
  - NÃO implementar REST API
  - NÃO usar `print()`/`typer.echo()` diretamente

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Lógica de importação CSV→DB temporário com múltiplas verificações de integridade, edge cases de parsing
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Sem UI
    - `git-master`: Sem operações git

  **Parallelization**:
  - **Can Run In Parallel**: YES (parallel with Task 11)
  - **Parallel Group**: Wave 3 (can run alongside Task 11, both depend on Wave 1+2)
  - **Blocks**: [Task 14]
  - **Blocked By**: [Tasks 1, 2] (schema migration + DB functions for `get_snapshot_by_path`)

  **References**:

  **Pattern References**:
  - `src/pipeline.py` — sub-app `pipeline_app` onde o comando será adicionado, seguir padrão existente de `ingest` command (flags, callback, CliFeedback)
  - `src/etl/snapshot.py:171-205` — `write_snapshot()` mostra como gerar CSV de snapshot; `restore-verify` faz o caminho inverso (CSV→DB)
  - `src/ingest/snapshot_ingest.py` — mostra padrão de ingestão CSV→DB, referência para batch insert

  **API/Type References**:
  - `src/db/snapshots.py` (Task 2) — `get_snapshot_by_path(conn, path)` retorna dict com metadados ou None
  - `src/utils/checksums.py:sha256_file()` — calcular checksum do arquivo CSV
  - `src/db/prices.py:read_prices()` — assinatura de referência para schema canônico de `prices`
  - `src/cli_feedback.py:CliFeedback` — usar para saída formatada

  **External References**:
  - Story spec: `docs/implementation-artifacts/2-6-verificacao-de-restauracao-a-partir-de-snapshot.md`

  **WHY Each Reference Matters**:
  - `src/pipeline.py` é onde o comando será adicionado — DEVE seguir padrão de CLI existente
  - `snapshot_ingest.py` mostra como fazer CSV→DB — referência para implementar a ingestão no DB temporário
  - `get_snapshot_by_path()` é a fonte de verdade para metadados — usar para comparação de checksum
  - `sha256_file()` é o checksum canônico — DEVE ser o mesmo usado em Story 2-2

  **Acceptance Criteria**:
  - [ ] Comando acessível via `poetry run python -m src.main pipeline restore-verify --help`
  - [ ] Com snapshot válido: importa para DB temp, executa 4 verificações, exit 0
  - [ ] Com checksum mismatch: exit 1 (WARN)
  - [ ] Com arquivo inexistente: exit 2 (FAIL)
  - [ ] Com colunas ausentes no CSV: exit 2 (FAIL)
  - [ ] Relatório JSON impresso com `overall_result`, `checks`, `rows_restored`

  **QA Scenarios**:

  ```
  Scenario: Restore-verify with valid snapshot produces PASS
    Tool: Bash
    Preconditions: Snapshot CSV gerado via pipeline snapshot (Task 3), metadata registrado na DB
    Steps:
      1. Run: poetry run python -m src.main pipeline restore-verify --snapshot-path snapshots/<ticker>-<ts>.csv
      2. Capture stdout — deve conter JSON report
      3. Parse JSON: verify overall_result == "PASS"
      4. Verify: rows_restored > 0
      5. Verify: checks.row_count == "pass", checks.columns_present == "pass", checks.checksum_match == "pass"
    Expected Result: JSON report com overall_result "PASS", exit code 0
    Failure Indicators: overall_result != "PASS", exit code != 0
    Evidence: .sisyphus/evidence/task-13-restore-verify-pass.txt

  Scenario: Restore-verify with nonexistent file produces FAIL
    Tool: Bash
    Steps:
      1. Run: poetry run python -m src.main pipeline restore-verify --snapshot-path /tmp/nonexistent.csv
      2. Capture stderr/stdout
    Expected Result: Error message via CliFeedback, exit code 2
    Failure Indicators: Exit code 0 or 1, nenhuma mensagem de erro
    Evidence: .sisyphus/evidence/task-13-restore-verify-missing-file.txt

  Scenario: Restore-verify with corrupted CSV produces FAIL
    Tool: Bash
    Preconditions: Criar CSV com colunas ausentes (ex: sem 'close')
    Steps:
      1. Create temp CSV missing required columns
      2. Run: poetry run python -m src.main pipeline restore-verify --snapshot-path /tmp/bad-snapshot.csv
      3. Parse output JSON
    Expected Result: checks.columns_present == "fail", overall_result == "FAIL", exit code 2
    Failure Indicators: overall_result != "FAIL", exit code != 2
    Evidence: .sisyphus/evidence/task-13-restore-verify-bad-columns.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(restore): add pipeline restore-verify CLI command (Story 2-6)`
  - Files: `src/pipeline.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

- [x] 14. Testes para Story 2-6 — Restore-Verify

  **What to do**:
  - Criar `tests/test_restore_verify.py` com os seguintes testes:
    1. `test_restore_verify_valid_snapshot_passes` — gerar snapshot via `write_snapshot()` com dados de fixture, registrar metadata na DB, invocar `restore-verify` via `CliRunner`, verificar JSON report com `overall_result == "PASS"` e exit code 0
    2. `test_restore_verify_checksum_mismatch_warns` — gerar snapshot, registrar metadata com checksum diferente na DB, invocar comando, verificar `overall_result == "WARN"` e exit code 1
    3. `test_restore_verify_missing_file_fails` — invocar com path inexistente, verificar exit code 2
    4. `test_restore_verify_missing_columns_fails` — criar CSV sem coluna `close`, invocar comando, verificar `checks.columns_present == "fail"` e exit code 2
    5. `test_restore_verify_row_count_matches` — gerar snapshot com N rows, verificar `rows_restored == N` no JSON report
    6. `test_restore_verify_temp_db_file` — invocar com `--temp-db /tmp/test-restore.db`, verificar que arquivo de DB é criado e contém dados
    7. `test_restore_verify_no_metadata_in_db` — snapshot sem metadata registrado na DB, verificar que `checksum_match` é "skip" ou "unavailable" (não crash)
  - Fixtures: usar `sample_db`, `tmp_path`, `create_prices_db_from_csv()` para popular DB com dados, `write_snapshot()` para gerar CSV
  - Invocar CLI via `typer.testing.CliRunner` seguindo padrão dos outros testes

  **Must NOT do**:
  - NÃO criar fixtures que dependam de rede
  - NÃO modificar `dados/data.db`
  - NÃO duplicar lógica de geração de snapshot — usar `write_snapshot()` existente

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Testes end-to-end com DB + FS + CLI, mas padrão claro de Tasks 5/6/9/10
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 13)
  - **Parallel Group**: Wave 3 (after Task 13)
  - **Blocks**: []
  - **Blocked By**: [Task 13]

  **References**:

  **Pattern References**:
  - `tests/test_pipeline_snapshot.py` (Task 5) — padrão de teste: `sample_db`, `CliRunner`, asserting exit codes, capturing output
  - `tests/conftest.py` — fixtures reusáveis

  **API/Type References**:
  - `src/pipeline.py` (Task 13) — comando `restore-verify` a ser testado
  - `src/etl/snapshot.py:write_snapshot()` — usar para gerar snapshot CSV nos testes
  - `src/db/snapshots.py` (Task 2) — `record_snapshot_metadata()` para inserir metadata nos testes

  **Test References**:
  - `tests/test_snapshot_metadata.py` (Task 6) — padrão de como inserir metadata e verificar
  - `tests/test_ci_validate_checksums.py` (Task 10) — padrão de teste para validação de checksums

  **WHY Each Reference Matters**:
  - `tests/test_pipeline_snapshot.py` é o modelo para testes de CLI pipeline — seguir EXATAMENTE o padrão
  - `write_snapshot()` gera CSV determinístico — usar nos testes para ter snapshot válido
  - `record_snapshot_metadata()` insere metadata na DB — usar para simular cenário com metadata disponível

  **Acceptance Criteria**:
  - [ ] `tests/test_restore_verify.py` existe com ≥ 7 test functions
  - [ ] `poetry run pytest tests/test_restore_verify.py -v` → all pass
  - [ ] Cobertura: PASS, WARN (checksum mismatch), FAIL (missing file, missing columns), row count, temp DB, no metadata

  **QA Scenarios**:

  ```
  Scenario: All Story 2-6 tests pass
    Tool: Bash
    Preconditions: Task 13 completed
    Steps:
      1. Run: poetry run pytest tests/test_restore_verify.py -v
      2. Verify all PASSED, exit code 0
    Expected Result: ≥ 7 tests pass, 0 failures
    Failure Indicators: Any FAILED test
    Evidence: .sisyphus/evidence/task-14-tests-story-2-6.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `test(restore): add tests for pipeline restore-verify command (Story 2-6)`
  - Files: `tests/test_restore_verify.py`
  - Pre-commit: `poetry run pre-commit run --all-files`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `poetry run pre-commit run --all-files` + `poetry run pytest`. Review all changed files for: `as any`, empty catches, `print()`/`typer.echo()` direto, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names. Verify line length ≤ 88 chars.
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Full CLI QA** — `unspecified-high`
  Start from clean state. Execute EVERY CLI command from EVERY story:
  1. `poetry run python -m src.main pipeline snapshot --ticker PETR4`
  2. `poetry run python -m src.main snapshots export --ticker PETR4 --format csv`
  3. `poetry run python -m src.main snapshots export --ticker PETR4 --format json`
  4. `poetry run python -m src.main snapshots purge --dry-run`
  5. `poetry run python -m src.main pipeline restore-verify --snapshot-path <path>`
  6. `python scripts/ci_validate_checksums.py`
  Test edge cases: invalid ticker, empty data, missing file. Save evidence to `.sisyphus/evidence/final-qa/`.
  Output: `Commands [6/6 pass] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual files changed. Verify 1:1 match — everything in spec built, nothing beyond spec added. Check "Must NOT do" compliance across ALL files. Check for `src/cli/` directory, SQLAlchemy imports, REST framework imports, `print()`/`typer.echo()` in new code. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Must NOT Have [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1 commit**: `feat(snapshots): add schema migration and snapshot generation from DB (Stories 2-1, 2-2)` — migrations/0002, src/db/snapshots.py, src/pipeline.py, src/etl/snapshot.py, tests
- **Wave 2 commit**: `feat(snapshots): add export CLI and CI checksum validation (Stories 2-3, 2-4)` — src/snapshot_cli.py, src/main.py, scripts/ci_validate_checksums.py, tests
- **Wave 3 commit**: `feat(snapshots): add retention purge and restore verification (Stories 2-5, 2-6)` — src/retention.py, src/snapshot_cli.py, src/pipeline.py, tests
- **Pre-commit for all**: `poetry run pre-commit run --all-files && poetry run pytest`

---

## Success Criteria

### Verification Commands
```bash
poetry run pytest                              # Expected: ALL tests pass (0 failures)
poetry run pre-commit run --all-files          # Expected: ALL hooks pass
poetry run python -m src.main pipeline snapshot --ticker PETR4  # Expected: CSV file in snapshots/
poetry run python -m src.main snapshots export --ticker PETR4 --format json  # Expected: JSON to stdout
poetry run python -m src.main snapshots purge --dry-run  # Expected: list of candidates, no deletion
python scripts/ci_validate_checksums.py        # Expected: exit 0 if checksums match
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All 6 stories' acceptance criteria met
- [ ] All tests pass (`poetry run pytest`)
- [ ] All lint passes (`poetry run pre-commit run --all-files`)
- [ ] Migration applies cleanly on existing DB
- [ ] No inline `CREATE TABLE IF NOT EXISTS` in `src/db/snapshots.py`
