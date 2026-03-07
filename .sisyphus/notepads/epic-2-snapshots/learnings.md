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

## [2026-03-07T02:00:00Z] Task 2: DB Query Functions

### Implementation Patterns
- **Connection handling**: All 5 functions follow exact pattern from `src/db/prices.py:read_prices()` — `conn or connect(db_path)`, cleanup in `finally` block only if we created connection
- **Row-to-dict conversion**: Used `dict(zip([col[0] for col in cur.description], row, strict=False))` pattern — `strict=False` required by ruff B905 (descriptor/row length mismatch possible with ALTER TABLE operations)
- **SQL parameterization**: Variable-length `IN` clause via `placeholders = ",".join("?" * len(snapshot_ids))` + unpacking (*snapshot_ids)
- **Archived timestamp**: `datetime.utcnow().isoformat()` for `archived_at` column when `mark_snapshots_archived()` runs

### Function Signatures Added
1. `get_snapshot_metadata(snapshot_id: str, *, conn=None, db_path=None) -> dict | None` — SELECT by ID
2. `list_snapshots(ticker: str | None = None, *, archived: bool = False, conn=None, db_path=None) -> list[dict]` — SELECT with optional ticker filter, ORDER BY created_at DESC
3. `mark_snapshots_archived(snapshot_ids: list[str], *, conn=None, db_path=None) -> int` — UPDATE archived=1, archived_at=timestamp, returns rowcount
4. `delete_snapshots(snapshot_ids: list[str], *, conn=None, db_path=None) -> int` — DELETE by ID list, returns rowcount
5. `get_snapshot_by_path(snapshot_path: str, *, conn=None, db_path=None) -> dict | None` — SELECT by snapshot_path column

### Code Changes to snapshots.py
- **Updated** `_upsert_snapshot_metadata()`: Added 5 columns to INSERT statement (`snapshot_path`, `rows`, `checksum`, `job_id`, `size_bytes`) from metadata dict via `.get()` calls
- **Added** `from datetime import datetime` import for archived_at timestamp generation
- **Added** 5 public functions to module (lines 137-316 in final file)

### Export Changes to src/db/__init__.py
- **Added** imports: `delete_snapshots`, `get_snapshot_by_path`, `get_snapshot_metadata`, `list_snapshots`, `mark_snapshots_archived`
- **Updated** `__all__` list to include 5 new functions (total 7 snapshot functions exported now)

### QA Test Results
- **Import test**: PASS — all 5 functions importable from `src.db` package
- **CRUD test**: PASS — full lifecycle verified (insert → read → list → archive → verify archived state)
- Evidence saved to `.sisyphus/evidence/task-2-imports.txt` and `task-2-crud-ops.txt`

### Critical Gotchas
- **Empty list handling**: Both `mark_snapshots_archived()` and `delete_snapshots()` return `0` immediately if `snapshot_ids` list is empty — avoids invalid SQL syntax
- **Ticker filter**: `list_snapshots()` accepts `ticker=None` to return ALL snapshots (only filtered by archived status)
- **Connection cleanup**: Pattern is `conn is None` check (NOT `close_conn` flag) — cleaner than legacy pattern in `get_last_snapshot_payload()`
- **Ruff B905**: `zip()` requires explicit `strict=` parameter — we use `strict=False` because SQL result sets from migrations might have mismatched lengths in edge cases

### Key Learning
- SQLite cursor.description returns list of 7-tuples `(name, type, display_size, internal_size, precision, scale, null_ok)` — we only need `col[0]` for column names
- UPDATE/DELETE operations require `.commit()` call before `cursor.rowcount` is accurate
- Variable-length parameter binding via f-string placeholders + tuple unpacking is safe (placeholders are literal `?` characters, not interpolated values)

## [2026-03-07T02:30:00Z] Task 3: Pipeline Snapshot Command

### CLI Command Patterns Applied
- Added `@app.command("snapshot")` directly in `src/pipeline.py` with typed options: `--ticker`, `--start`, `--end`, `--output-dir`
- Reused `_normalize_cli_ticker()` for consistent B3 ticker validation behavior
- All user-facing command output goes through `CliFeedback` (`start`, `error`, `success`), avoiding `print()`/`typer.echo()`

### Execution Flow Decisions
- Snapshot generation is DB-first (`db.read_prices`) and never pulls provider/network data
- Output directory selection follows `Path(output_dir) if output_dir else SNAPSHOTS_DIR`, with `mkdir(parents=True, exist_ok=True)`
- Metadata checksum uses `sha256_file(out_path)` (file bytes), not DataFrame checksum helpers

### Runtime Gotcha Found During Verification
- `record_snapshot_metadata()` failed initially on local `dados/data.db` because migration `0002_expand_snapshots.sql` had not yet been applied in that environment (`snapshot_path` column missing)
- Resolved in command flow by calling `db.init_db(db_path=None)` before reading prices/recording snapshot metadata, ensuring schema+migrations are applied idempotently

### Verification Outcomes
- Valid call `pipeline snapshot --ticker PETR4` exits successfully and writes `snapshots/PETR4_snapshot.csv`
- Invalid ticker/range equivalent (`ZZZZ99`) returns exit code 1 with `CliFeedback.error`
- Metadata row for PETR4 is persisted with expanded schema fields available (`snapshot_path`, `rows`, `checksum`, `size_bytes`, `archived`, `archived_at`)

### Final Adjustment
- Removed temporary `db.init_db()` call from command flow to keep strict requirement scope (normalize → read DB → validate → write snapshot → register metadata), assuming migration baseline from Task 1 is already applied in target environment

## [2026-03-07T02:18:30Z] Task 4: Idempotency Fix

### Root-Cause Correction
- `_upsert_snapshot_metadata()` previously generated `job_id` from `json.dumps(metadata, sort_keys=True)`, which included volatile fields (`created_at`) and broke idempotency.
- Implemented deterministic ID generation with stable inputs only: `ticker`, `start`, `end`.
- New stable key pattern: `f"{ticker}_{start}_{end}"` hashed with SHA256.

### Stable Field Resolution Strategy
- Added `_extract_date_range_from_payload(metadata)` to resolve `start/end` in this order:
  1. Top-level metadata keys (`start`/`start_date`, `end`/`end_date`)
  2. Nested `payload` (dict or JSON string)
  3. Date-like tokens from `snapshot_path` (regex fallback)
- If range is unavailable, fallback still remains deterministic (`ticker__`).

### Behavioral Outcome
- Kept SQL statement unchanged (`INSERT OR REPLACE INTO snapshots(...)`) as required.
- Second run for same ticker/range now reuses the same primary key and replaces row content instead of inserting a duplicate.
- Verified replacement semantics: row count unchanged on second run, `id` unchanged, `created_at` updated.

### Validation Results
- `lsp_diagnostics` reports no errors for `src/db/snapshots.py`.
- `poetry run pytest -xvs tests/` passed: **222 passed**.
- Evidence saved to `.sisyphus/evidence/task-4-idempotency-fixed.txt`.

## Task 5 — Tests for Story 2-1 (`pipeline snapshot` CLI) — 2026-03-07

### Implementation Bug Discovered and Fixed

**Bug**: `pipeline snapshot` command dropped the `date` column from CSV output.

**Root Cause**:
- `db.read_prices()` returns DataFrame with `date` as **index** (line 183 of `src/db/prices.py`)
- `write_snapshot()` calls `serialize_df_bytes(df, index=False)` (line 183 of `src/etl/snapshot.py`)
- Writing with `index=False` discards the date index

**Fix Applied** (line 201 of `src/pipeline.py`):
```python
# Before
_ = write_snapshot(df, out_path)

# After
_ = write_snapshot(df.reset_index(), out_path)
```

**Impact**: Ensures all snapshot CSVs include the `date` column as required by canonical schema.

### Test Monkeypatch Strategy for Date Filtering

**Challenge**: CLI command `db.read_prices()` uses internal `_connect()` function. Simple monkeypatching of `db.connect` was insufficient.

**Solution**: Monkeypatch both the public API **and** the internal implementation:

```python
from src import db
from src.db import prices

# Patch the internal _connect used by read_prices
monkeypatch.setattr(prices, "_connect", lambda db_path=None: sample_db)

# Patch the public API for metadata recording
monkeypatch.setattr(db, "connect", lambda **kw: sample_db)
```

**Why Both**:
- `src.db.prices` imports `_connect` from `src.db.connection` (line 13)
- `read_prices()` calls `_connect(db_path)` directly when no `conn` parameter provided (line 123)
- Metadata recording via `db.record_snapshot_metadata()` may also need DB connection

**Pattern Applied**: When testing CLI commands that use DB layer, patch:
1. The internal `_connect` in the specific module being used
2. The public `db.connect` for any indirect calls

### CSV Column Structure Verified

**Actual Snapshot Columns** (sorted alphabetically by `serialize_df_bytes`):
```
['close', 'date', 'fetched_at', 'high', 'low', 'open', 'raw_checksum', 'source', 'ticker', 'volume']
```

**Core Canonical Columns**:
```
['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
```

**Internal Columns** (not part of core schema but included in snapshot):
```
['source', 'fetched_at', 'raw_checksum']
```

**Test Strategy**: Verify presence of core columns (not exact match) to allow for internal metadata columns.

### Test Coverage Achieved

All 7 required test functions implemented and passing:

1. ✅ `test_snapshot_generates_csv_file` — Basic functionality
2. ✅ `test_snapshot_csv_has_correct_columns` — Schema validation (core columns present)
3. ✅ `test_snapshot_with_date_range` — `--start`/`--end` filtering works correctly
4. ✅ `test_snapshot_invalid_ticker_exit_code_1` — Error handling for unknown ticker
5. ✅ `test_snapshot_empty_date_range_exit_code_1` — Error handling for empty result set
6. ✅ `test_snapshot_creates_output_dir` — Directory creation when missing
7. ✅ `test_snapshot_default_output_dir` — Uses `SNAPSHOTS_DIR` constant by default

**Testing Approach**:
- Used `CliRunner` from Typer for CLI invocation
- Used `sample_db` fixture for test data (5 rows, PETR4.SA, dates 2023-01-02 to 2023-01-06)
- Used `tmp_path` fixture for output isolation (NOT session `snapshot_dir`)
- Applied monkeypatch for both `_connect` and `connect` functions
- Verified CSV structure, exit codes, error messages, and file creation

### Related Tests Still Pass

- `tests/test_cli.py`: 10 tests passing
- `tests/test_snapshot.py`: 2 tests passing

No regressions introduced by the `df.reset_index()` fix.

## [2026-03-07T03:25:00Z] Task 7: Implement `snapshots export` CLI Command (Story 2-3)

### Implementation Decisions
- Created `src/snapshot_cli.py` as a standalone Typer sub-app (`app = typer.Typer()`), keeping the flat `src/` CLI structure.
- Added `export` command with required options `--ticker`, `--format`, and `--output`.
- Used `db.list_snapshots(ticker=..., archived=False)` and selected the first row as latest snapshot (`created_at DESC` ordering from Task 2 contract).
- Implemented path resolution that supports both absolute `snapshot_path` metadata and relative paths under `SNAPSHOTS_DIR`.
- Implemented CSV export as plain CSV bytes to stdout/file with `index=False`.
- Implemented JSON export with `records` orientation and metadata wrapper:
  `{"ticker": ..., "checksum": ..., "rows": ..., "data": [...]}`.
- Mounted sub-app in `src/main.py` with `app.add_typer(snapshot_cli_module.app, name="snapshots")`.

### Gotchas Encountered
- `CliFeedback` default methods route several statuses to stdout (`start`, `success`, `warn`).
  To preserve strict stdout=data and stderr=status separation for export output,
  Task 7 uses a small local subclass overriding those methods with `err=True`.
- Needed explicit format normalization (`strip().lower()`) and ticker normalization
  (`strip().upper()`) to avoid invalid-format/ticker edge behavior.

## [2026-03-07T03:29:00Z] Task 8: CI Checksum Validation Script (Story 2-4)

### Implementation Decisions

**Script Structure**:
- Created `scripts/ci_validate_checksums.py` as standalone CI utility (NOT Typer command)
- Followed `scripts/validate_snapshots.py` pattern for consistency:
  - Shebang: `#!/usr/bin/env python3`
  - `sys.path` manipulation for imports when run directly
  - `main()` function with explicit return type
  - `if __name__ == "__main__": raise SystemExit(main())`

**Checksum Function Selection**:
- Used `sha256_file()` from `src.utils.checksums` (lines 25-38)
- CRITICAL: NOT `snapshot_checksum()` — different algorithms produce different hashes
- Matches Story 2-2 (Task 3) implementation — validates what pipeline actually stores

**DB Query Pattern**:
- Used `db.list_snapshots(archived=False, conn=conn)` from Task 2
- Returns list of dicts with all required fields (id, ticker, snapshot_path, checksum)
- Connection cleanup in `finally` block (established pattern from Task 2)

**Output Format**:
- Structured text with clear PASS/FAIL markers per snapshot
- Summary section with counts: total, passed, failed, missing
- Exit codes: 0 = all pass, 1 = any failures
- Explicit "Exit code: X" in output for CI transparency

### Edge Cases Handled

1. **No snapshots in DB**: Returns exit 0 with message "No snapshots to validate"
2. **Incomplete metadata**: Skips snapshots without `snapshot_path` or `checksum` (lines 60-63)
3. **Missing file**: Reports FAIL with "File not found" message, increments failure count
4. **Checksum mismatch**: Shows expected vs computed hashes, increments failure count

### Gotchas Encountered

**LSP Warnings About Implicit String Concatenation**:
- Lines 69, 79, 85: Multi-line f-strings without explicit `+` operator
- Pattern already accepted in codebase (see `scripts/validate_snapshots.py`)
- Warnings only, no errors — acceptable for CI scripts

**Real DB Contains Mismatches**:
- Testing revealed 4 snapshots with checksum mismatches from prior development
- Script correctly detected and reported these (validation working as intended)
- Demonstrates script catches real integrity issues

### Key Learnings

**Script vs CLI Command Decision**:
- CI validation scripts should be standalone (NOT Typer commands)
- Reason: Simpler to invoke in CI workflows, no CLI framework overhead
- Pattern: Use scripts for CI-specific tasks, CLI commands for user-facing operations

**Connection Handling in Scripts**:
- Always use `try/finally` for DB connections (even in scripts)
- Pattern established in Task 2, consistently applied in Task 8
- Prevents connection leaks in CI environments

**Exit Code Semantics**:
- 0 = success (all validations passed OR nothing to validate)
- 1 = failure (any checksum mismatch or missing file)
- No warnings/partial success — binary pass/fail for CI clarity

**Checksum Validation Pattern**:
- File-based checksum (`sha256_file`) is source of truth for snapshot integrity
- DataFrame-based checksum (`snapshot_checksum`) is for in-memory validation only
- Never mix the two — Task 1-7 learnings remain critical

---

## Task 9: Test `snapshots export` CLI Command (Story 2-3)

### Test Implementation Findings

**DB Isolation in CLI Tests Requires Multi-Level Patching**:
- Initial attempt: patched only `connection._connect` → failed (stale DB access)
- Root cause: `db.list_snapshots()` imports `_connect` from `src.db.snapshots` module
- Solution: patch at THREE locations simultaneously:
  ```python
  from src.db import connection, snapshots
  monkeypatch.setattr(connection, "_connect", lambda db_path=None: conn)
  monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: conn)
  monkeypatch.setattr(db, "connect", lambda **kw: conn)
  ```
- Pattern from `tests/test_pipeline_snapshot.py` line 96 (reference test)
- Lesson: When testing CLI commands that invoke DB operations, patch `_connect` at ALL import sites where it's used

**CSV Column Order Not Guaranteed by pandas**:
- Test assumed specific column order: `date,open,high,low,close,adj_close,volume`
- Actual output: `adj_close,close,date,high,low,open,volume` (alphabetical)
- Cause: `df.to_csv(index=False)` uses DataFrame's column order (alphabetical from test setup)
- Fix: Changed assertion to check for column presence, not specific order:
  ```python
  assert "date" in header and "open" in header and "close" in header
  ```
- Lesson: Test CSV structure semantically (presence, data values) not syntactically (exact order)

**Integer vs Float Formatting in CSV Export**:
- Test expected `"10.0"` (float with decimal)
- CSV contained `10` (integer without decimal) and `10.5` (float)
- Pandas infers dtype from data: integer columns stay integers in CSV
- Fix: Relaxed assertion to accept both formats: `"10," in result or "10.0" in result`
- Lesson: Don't assume decimal formatting in CSV—pandas optimizes dtype representation

**Test DB Schema Initialization Pattern**:
- Helper function `_setup_snapshot` must CREATE TABLE explicitly
- Cannot rely on production migrations/fixtures
- Pattern: Each test starts with clean schema in `tmp_path / "test.db"`
- Schema from `migrations/0000_init_schema.sql` and `0002_expand_snapshots.sql`

**Test Baseline Verification**:
- Starting baseline: 235 tests passing (from Task 8)
- Added: 7 new tests in `test_snapshots_export.py`
- Final baseline: **242 tests passing** (all pass, no failures)
- Evidence file: `.sisyphus/evidence/task-9-tests-story-2-3.txt`

### Key Learnings

**CLI Test Isolation Strategy**:
- Use per-test `tmp_path` instead of session fixtures (as per task instructions)
- Patch DB connection functions BEFORE importing CLI modules
- Patch at all relevant import locations (not just one entry point)
- Always close connections in `try/finally` blocks

**CliRunner Behavior with pytest**:
- CliRunner doesn't support `mix_stderr=False` parameter (invalid API)
- Use `result.stdout` for stdout-only assertions
- Use `result.output` for combined stdout+stderr assertions
- Status messages go to stderr by design (`typer.echo(..., err=True)`)

**Test Coverage Achieved**:
1. ✅ CSV export to stdout with stderr status messages
2. ✅ JSON export with metadata wrapper and records orientation
3. ✅ File output via `--output` flag (CSV format)
4. ✅ File output via `--output` flag (JSON format)
5. ✅ Exit code 1 for unknown ticker
6. ✅ JSON metadata fields validation (`ticker`, `checksum`, `rows`, `data`)
7. ✅ CLI mounting verification (`snapshots export --help` works from main app)

**Checksum File Naming Convention**:
- Checksum sidecar file: `{snapshot_path}.checksum` (full path + `.checksum`)
- NOT `{snapshot_filename_without_ext}.checksum`
- Example: `PETR4-20260307T034204Z.csv.checksum`

**Snapshot Filename Pattern** (from Task 3):
- Format: `{ticker}-{timestamp}Z.csv`
- Example: `PETR4-20260307T034204Z.csv`
- Timestamp: ISO 8601 UTC format with `Z` suffix

## Task 10: Test Suite for CI Checksum Validation Script (2026-03-07)

### Goal
Create comprehensive pytest test suite for `scripts/ci_validate_checksums.py` (CI checksum validation script) with ≥5 test functions covering all validation scenarios.

### Critical Discovery: Correct Mocking Pattern for Script Testing

**Problem**: Initial mock implementation caused infinite recursion:
```python
def mock_connect(db_path=None):
    return db.connect(db_path=str(tmp_path / "test.db"))  # ← calls itself!
```

**Root Cause**: Mock function called `db.connect()` which was already patched to call the mock → infinite loop.

**Solution Pattern (from Task 9)**:
1. Create real connection FIRST (outside mock)
2. Patch multiple import locations (connection, snapshots, db modules)
3. Return same connection object in all patches
4. Import script AFTER patching

```python
# 1. Create connection FIRST
test_db_path = str(tmp_path / "test.db")
test_conn = db.connect(db_path=test_db_path)

# 2. Import submodules
from src.db import connection, snapshots

# 3. Patch multiple locations
monkeypatch.setattr(connection, "_connect", lambda db_path=None: test_conn)
monkeypatch.setattr(snapshots, "_connect", lambda db_path=None: test_conn)
monkeypatch.setattr(db, "connect", lambda **kw: test_conn)

# 4. Import script AFTER patches
from scripts.ci_validate_checksums import main
```

### Test Coverage Achieved
- **7 test functions** (442 lines → 463 lines after mocking fixes)
- **All tests pass** (7/7 passed in 0.31s)
- **Scenarios covered**:
  1. `test_valid_checksums_pass` - all checksums match → exit 0
  2. `test_tampered_file_fails` - file modified after checksum → exit 1
  3. `test_missing_file_fails` - snapshot_path doesn't exist → exit 1
  4. `test_no_snapshots_passes` - empty DB → exit 0
  5. `test_output_format_shows_results` - stdout format validation
  6. `test_archived_snapshots_ignored` - archived=1 snapshots skipped
  7. `test_snapshots_without_checksum_skipped` - NULL checksum skipped

### Key Implementation Details
- **Helper functions**: `_create_snapshots_table()`, `_insert_snapshot_metadata()`
- **Test isolation**: Each test uses `tmp_path` fixture for separate DB
- **Checksum computation**: Uses `sha256_file()` from `src.utils.checksums`
- **Output validation**: Uses `capsys` fixture to capture stdout
- **Script interface**: `main() -> int` (returns exit code 0/1)

### Evidence
- Test output: `.sisyphus/evidence/task-10-tests-story-2-4.txt`
- Test file: `tests/test_ci_validate_checksums.py` (463 lines)

### Pattern for Future Script Testing
When testing scripts that use `db.connect()`:
1. Create real test DB connection FIRST
2. Patch all import locations (connection, snapshots, db)
3. Use lambda returning same connection object
4. Import script AFTER monkeypatch setup
5. Never create mocks that call the function being mocked

This pattern prevents infinite recursion and ensures tests use isolated test databases.
