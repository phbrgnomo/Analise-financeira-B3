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
# ETL/DB Wave1 scan - 2026-03-23T19:14:37Z
Found mapper.parse_date_strict in src/etl/mapper.py; prices.read/write in src/db/prices.py; snapshot ingest in src/ingest/snapshot_ingest.py; ingest pipeline in src/ingest/pipeline.py


# Context gathered 2026-03-23T19:XX UTC - ALL 4 agents

## Streamlit app (bg_615d8efa)
- st.session_state: NOT USED — stateless app
- No fuzzy/autocomplete — just selectbox + text_input
- No "Buscar dados" button — absent
- Data flow: _sidebar_and_inputs → load_prices → _safe_line_chart
- Migration: 0000, 0001, 0002 exist. Next is 0003.
- to_canonical in mapper.py is the canonical mapper (map_row_to_ohlc doesn't exist as separate function)
- delete_ticker_prices() does NOT exist in src/db/prices.py — needs to be added

## Wave1 code map (bg_678eaab4)
- parse_date_strict: IMPLEMENTED ✓
- detect_outlier: MISSING — needs implementation
- upsert_staging/commit/rollback: MISSING — write_prices handles transactional inline
- ensure_prices: MISSING — _ensure_schema exists in schema.py but not the service wrapper
- src/services/ directory: DOES NOT EXIST — needs to be created
- src/db/prices.py: write_prices (lines 20-146), read_prices (149-263), list_price_tickers (265-279)
- src/ingest/pipeline.py: ingest() (lines 416-603)
- src/ingest/snapshot_ingest.py: ingest_from_snapshot (513-641), rows_to_ingest (130-184)

## Services/schema (bg_347074d0) - collected via bg_678eaab4
- adapters/factory.py: available_providers() exists
- get_adapter() exists
- src/db/schema.py: _ensure_schema, _get_upsert_sql
- src/db/prices.py: no delete_ticker_prices — must add

## Streamlit librarian patterns (bg_7d31685b)
- Enter key: use st.form + st.form_submit_button
- Fuzzy suggestions: st.container + st.button in columns, st.session_state
- Debounce 300ms: use streamlit-keyup component OR client-side widget
  - NO debounce in vanilla Streamlit — components required
- Stop/cancel: toggle st.session_state.running with on_click callback
- Dynamic title: st.set_page_config + st.rerun()
- Provider selectbox: adapter factory pattern (already in codebase)

## Wave 1 task numbering (from plan)
T1=T3 in plan (high/low swap), T2=T4 (CHECK), T3=T5 (index), T4=T6 (outlier), T5=T7 (staging), T6=T8 (ensure_prices)
Note: plan uses "T3-T8" in execution plan to mean these 6 tasks.

Added migration 0004_add_idx_prices_ticker_date.sql to create composite index on
prices(ticker, date DESC) for faster "latest first" queries by ticker + date
range. Verified in-memory SQLite EXPLAIN QUERY PLAN shows the index is used.
