-- Migration 0001: create returns table
CREATE TABLE IF NOT EXISTS returns (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    return_value REAL NOT NULL,
    return_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(ticker, date, return_type)
);
