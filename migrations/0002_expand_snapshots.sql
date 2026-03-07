-- Migration 0002: expand snapshots table with metadata columns
-- Each ALTER TABLE statement adds one column to avoid SQLite limitations
-- (SQLite does not support adding multiple columns in a single ALTER TABLE)

ALTER TABLE snapshots ADD COLUMN snapshot_path TEXT;

ALTER TABLE snapshots ADD COLUMN rows INTEGER;

ALTER TABLE snapshots ADD COLUMN checksum TEXT;

ALTER TABLE snapshots ADD COLUMN job_id TEXT;

ALTER TABLE snapshots ADD COLUMN size_bytes INTEGER;

ALTER TABLE snapshots ADD COLUMN archived BOOLEAN DEFAULT 0;

ALTER TABLE snapshots ADD COLUMN archived_at TEXT;
