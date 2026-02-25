-- Migration 0000: initialize core schema (prices, metadata, snapshots)
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume INTEGER,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    raw_checksum TEXT NOT NULL,
    PRIMARY KEY (ticker, date)
);

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
