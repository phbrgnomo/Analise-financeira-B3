-- Migration 0001: create returns table
CREATE TABLE IF NOT EXISTS returns (
    ticker TEXT,
    date TEXT,
    return_value REAL,
    return_type TEXT,
    created_at TEXT,
    PRIMARY KEY (ticker, date, return_type)
);
