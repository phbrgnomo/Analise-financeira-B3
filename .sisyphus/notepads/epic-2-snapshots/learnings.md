# Epic 2 Snapshots — Learnings

## Architecture Patterns
- **CLI structure**: Flat in `src/` (no `src/cli/` directory). Sub-apps mounted via `app.add_typer()` in `src/main.py`
- **DB layer**: Raw `sqlite3`, every function accepts optional `conn`/`db_path`
- **Migration system**: SQL files in `migrations/` directory, tracked by `src/db_migrator.py` with `schema_migrations` table
- **Output feedback**: All CLI output via `CliFeedback` (routes to stderr), NO direct `print()`/`typer.echo()`
- **Line length**: 88 chars max (ruff config)

## Key Implementation Conventions
- **Checksum for metadata**: Use `sha256_file()` (file bytes) NOT `snapshot_checksum()` (DataFrame serialization) — different algorithms, different values
- **Retention model**: 2 states only — `active` (archived=0) and `archived` (archived=1). No multi-tier complexity
- **JSON orientation**: Use `records` format for JSON export
- **Test strategy**: Tests-after pattern, use `sample_db` fixture, `tmp_path` for isolation
- **Idempotency**: `INSERT OR REPLACE` for snapshot metadata — same ticker/period should not duplicate rows

## Critical Discoveries
- `write_snapshot()` already writes `.checksum` sidecar — don't duplicate
- `_prune_old_snapshots()` already handles basic retention (keep N latest) — extend with time-based policy
- `ingest-snapshot` does CSV→DB (opposite direction of Story 2-1 which is DB→CSV)
- TWO checksum mechanisms coexist: `sha256_file()` vs `serialize_df_bytes()` — they produce DIFFERENT hashes
- `_upsert_snapshot_metadata()` has inline `CREATE TABLE` that must be removed after migration

## Resolved Design Decisions
- **Migration approach**: SQL file (`0002_expand_snapshots.sql`) via `db_migrator.py`, NOT PRAGMA user_version
- **Retention config**: Single env var `SNAPSHOT_RETENTION_DAYS` (default 90), no `keep_monthly`/`keep_yearly`/`min_free_space_mb`
- **`job_id` generation**: Reuse existing SHA256-of-metadata pattern in `_upsert_snapshot_metadata()`

## [2026-03-07T01:40:00Z] Task 1: Schema Migration (0002_expand_snapshots)

### Migration File Structure
- Created `migrations/0002_expand_snapshots.sql` with 7 separate `ALTER TABLE` statements
- Naming convention: `{sequence}_{description}.sql` matches existing patterns
- Each column added via individual ALTER statement (SQLite 3.25.0+ supports this but project uses separate statements for clarity)
- Comment explains SQLite column-adding constraint — necessary for maintainability
- Columns added: `snapshot_path TEXT`, `rows INTEGER`, `checksum TEXT`, `job_id TEXT`, `size_bytes INTEGER`, `archived BOOLEAN DEFAULT 0`, `archived_at TEXT`

### Code Changes to snapshots.py
- **Removed** (lines 77-86): Inline `CREATE TABLE IF NOT EXISTS snapshots` block that duplicated 0000_init_schema.sql
- **Kept** (line 88): `CREATE INDEX IF NOT EXISTS snapshots_ticker_created_at_idx` — idempotent, safe to run multiple times
- Inline CREATE TABLE removal required sqlparse dependency install via `poetry add sqlparse --group dev`

### Testing Verification
- **Fresh DB test**: Migration applies successfully to in-memory DB, all 7 columns appear in `PRAGMA table_info(snapshots)` output
- **Snapshot metadata context**: Job ID generation reuses existing SHA256 pattern from metadata dict, no changes needed to logic
- Evidence saved to `.sisyphus/evidence/task-1-migration-fresh-db.txt` and `task-1-no-inline-create.txt`
- All columns verified present: `snapshot_path`, `rows`, `checksum`, `job_id`, `size_bytes`, `archived`, `archived_at`
- Existing columns preserved: `id`, `ticker`, `created_at`, `payload`

### Key Learning
- `db_migrator.apply_migrations()` requires sqlparse to safely parse complex SQL files
- Poetry dependency installation works correctly; no environment reconstruction needed
- ALTER TABLE approach (7 statements) is correct for SQLite; migration applies in alphabetical order (0000 → 0001 → 0002)
