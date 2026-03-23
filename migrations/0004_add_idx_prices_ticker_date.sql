-- Migration 0004: add composite index on prices(ticker, date DESC)
-- Optimizes queries by ticker + date range
-- Supports DESC order for "latest first" queries
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date
  ON prices(ticker, date DESC);
