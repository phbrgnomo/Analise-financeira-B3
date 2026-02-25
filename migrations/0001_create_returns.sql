-- Migration 0001: create returns table
CREATE TABLE IF NOT EXISTS returns (
    ticker TEXT,
    date TEXT,
    return REAL,
    return_type TEXT,
    created_at TEXT,
    UNIQUE(ticker, date, return_type)
);
