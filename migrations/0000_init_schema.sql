-- Migration 0000: initialize core schema (prices, metadata, snapshots)
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    raw_checksum TEXT NOT NULL,
    PRIMARY KEY (ticker, date)
);

-- Index to speed up queries that filter only by `ticker`.
-- PRIMARY KEY (ticker, date) is good for range queries, but a separate
-- index on `ticker` improves performance for ticker-only lookups.
CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    ticker TEXT,
    created_at TEXT,
    payload TEXT
);

COMMIT;

-- Reativar verificação de chaves estrangeiras para operações subsequentes
PRAGMA foreign_keys = ON;
