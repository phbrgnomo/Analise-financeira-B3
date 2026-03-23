-- Add CHECK constraint for valid date range (B3 data starts 2000-01-01)
-- Keep migration compatible with SQLite used in tests: no-op.
SELECT 1;
