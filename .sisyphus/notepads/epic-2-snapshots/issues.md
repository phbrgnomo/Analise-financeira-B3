# Issues Log — Epic 2 Snapshots

## [2026-03-07T02:20:00Z] Task 2: Test Regression from Task 1

**Test**: `tests/test_ingest_cache_incremental.py::test_snapshot_index_created` (lines 159-181)

**Error**: `sqlite3.OperationalError: no such table: main.snapshots` at `src/db/snapshots.py:78`

**Root Cause**: Task 1 removed inline `CREATE TABLE IF NOT EXISTS snapshots` from `_upsert_snapshot_metadata()` (lines 77-86 in `src/db/snapshots.py`) because schema is now managed by migrations (`migrations/0002_expand_snapshots.sql`). Test assumed `record_snapshot_metadata()` would create table automatically (original comment line 168: "no need to call init_db; record_snapshot_metadata will create table").

**Fix Applied**: Updated test lines 167-172 to call `init_db() + apply_migrations()` before `record_snapshot_metadata()`:

```python
_db.init_db(db_path=str(db_path))  # Creates 0000 schema
conn = _db.connect(db_path=str(db_path))
apply_migrations(conn)  # Applies 0001, 0002
conn.close()
```

**Learning**: All tests calling `record_snapshot_metadata()` must now initialize DB and run migrations first. This is the correct pattern going forward for any test that writes to the `snapshots` table.

**Verification**: Test now passes (`poetry run pytest tests/test_ingest_cache_incremental.py::test_snapshot_index_created -xvs`).

**Impact**: This pattern change affects ALL future tests in Epic 2 (Waves 1-3) that interact with the `snapshots` table. Tests must use:
```python
from src import db
from src.db_migrator import apply_migrations

 db.init_db(db_path=str(db_path))
 conn = db.connect(db_path=str(db_path))
 apply_migrations(conn)
 conn.close()
 # ... then use db.record_snapshot_metadata() or other snapshot DB functions
 ```

## [2026-03-07T06:05:00Z] Task F4: Scope Fidelity Rejection Findings

**Scope fidelity outcome**: REJECT (11/14 compliant)

**Non-compliant tasks identified**:
1. **Task 4 (partial)**: payload enrichment requirement not fully reflected in metadata population path
2. **Task 6**: task guardrail said not to test CLI flow, but tests call CLI command directly
3. **Task 7**: direct `typer.echo()` introduced in new CLI module (`src/snapshot_cli.py:33`)

**Must-NOT violation**:
- New CLI code still contains direct `typer.echo()` usage (`src/snapshot_cli.py:33`)

**Unaccounted changes detected**:
- `.sisyphus/plans/epic-2-snapshots.md` modified despite read-only rule
- `.sisyphus/boulder.json`, `pyproject.toml`, `poetry.lock`, `tests/test_ingest_cache_incremental.py`, `dados/data.db` drifted outside explicit Task 1-14 deliverables

**Recorded verdict artifact**:
- `.sisyphus/evidence/final-f4-scope-fidelity.txt`
