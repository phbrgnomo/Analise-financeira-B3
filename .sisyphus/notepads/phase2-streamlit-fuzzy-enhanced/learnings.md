Added parse_date_strict(date_str) to src/etl/mapper.py that:
- Parses only YYYY-MM-DD strings (strict), accepts datetime/Timestamp too.
- Normalizes to UTC-aware datetime at midnight.
- Rejects future dates and dates before 2000-01-01.
- Integrated validation into mapper._fill_special_values for `date` column;
  invalid/unsupported values are logged and replaced with NaT so
  pandera validation can surface row-level issues.

Tests added: tests/unit/test_etl_optimizations.py covering valid,
invalid-format, future-date, and pre-2000 rejections.

Notes:
- Kept implementation dependency-free (stdlib + pandas already in project).
- Followed existing logging conventions (logger.warning).
