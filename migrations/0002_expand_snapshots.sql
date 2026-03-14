-- Migration 0002: expand snapshots table with metadata columns
-- Each ALTER TABLE statement adds one column to avoid SQLite limitations
-- (SQLite does not support adding multiple columns in a single ALTER TABLE)

ALTER TABLE snapshots ADD COLUMN snapshot_path TEXT;

-- index to accelerate queries by path (used by get_snapshot_by_path)
CREATE INDEX IF NOT EXISTS snapshots_snapshot_path_idx
    ON snapshots(snapshot_path);

-- index to accelerate queries by ticker + created_at (used by incremental cache and other lookups)
CREATE INDEX IF NOT EXISTS snapshots_ticker_created_at_idx
    ON snapshots(ticker, created_at);

ALTER TABLE snapshots ADD COLUMN rows INTEGER;

ALTER TABLE snapshots ADD COLUMN checksum TEXT;

ALTER TABLE snapshots ADD COLUMN job_id TEXT;

ALTER TABLE snapshots ADD COLUMN size_bytes INTEGER;

ALTER TABLE snapshots ADD COLUMN archived BOOLEAN DEFAULT 0;

ALTER TABLE snapshots ADD COLUMN archived_at TEXT;
