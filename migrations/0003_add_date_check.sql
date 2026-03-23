-- Add CHECK constraint for valid date range (B3 data starts 2000-01-01)
-- Must not contain data outside this range or future dates
ALTER TABLE prices ADD CONSTRAINT chk_prices_date_range
  CHECK (date >= '2000-01-01' AND date <= CURRENT_DATE);
