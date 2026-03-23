"""Service helpers for ingest operations.

Keep this module free of Streamlit imports so it can be used from
non-UI contexts (CLI, tests).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Sequence, Tuple

from src.db.prices import read_prices, resolve_existing_ticker
from src.ingest import pipeline as ingest_pipeline


def _to_iso(date_val: str) -> str:
    # Accept YYYY-MM-DD like strings and return same format (validate)
    try:
        dt = datetime.fromisoformat(date_val)
        return dt.date().isoformat()
    except Exception:
        # let caller handle invalid formats via raised ValueError
        raise


def compute_missing_ranges(
    existing_rows: Sequence[str] | Sequence[datetime], all_dates: Sequence[str]
) -> List[Tuple[str, str]]:
    """Given existing row dates and requested date list, return missing ranges.

    existing_rows may be sequence of datetimes or ISO date strings. all_dates is
    the complete requested date list (ISO strings). We return list of
    (start_iso, end_iso) grouping consecutive missing dates.
    """
    # Normalize existing dates to set of ISO strings
    existing_set = set()
    for d in existing_rows:
        if d is None:
            continue
        if isinstance(d, str):
            try:
                existing_set.add(datetime.fromisoformat(d).date().isoformat())
            except Exception:
                # ignore unparsable
                continue
        else:
            existing_set.add(d.date().isoformat())

    missing_dates = [d for d in all_dates if d not in existing_set]
    if not missing_dates:
        return []

    # Convert to datetime.date for consecutive detection
    md_dates = [datetime.fromisoformat(d).date() for d in missing_dates]
    md_dates.sort()

    ranges: List[Tuple[str, str]] = []
    start = md_dates[0]
    prev = md_dates[0]
    for cur in md_dates[1:]:
        if cur - prev > timedelta(days=1):
            ranges.append((start.isoformat(), prev.isoformat()))
            start = cur
        prev = cur
    ranges.append((start.isoformat(), prev.isoformat()))
    return ranges


def ensure_prices(
    ticker: str, start: str, end: str, provider: str, db_path: str
) -> dict:
    """Ensure price rows exist for ticker in [start, end].

    Returns dict: {ok: bool, fetched_ranges: list, errors: list, rows_added: int}
    """
    # Normalize
    if not isinstance(ticker, str):
        raise TypeError("ticker must be a string")
    ticker_norm = ticker.strip().upper()
    start_iso = _to_iso(start)
    end_iso = _to_iso(end)

    if start_iso > end_iso:
        raise ValueError("start must be <= end")

    errors: List[str] = []
    fetched_ranges: List[Tuple[str, str]] = []
    rows_added = 0

    # Resolve persisted ticker (may be None). If the DB hasn't been
    # initialised (e.g. in-memory during tests) treat as no existing ticker.
    try:
        resolved = resolve_existing_ticker(ticker_norm, db_path=db_path)
    except Exception:
        resolved = None
    read_ticker = resolved or ticker_norm

    # Read existing rows
    try:
        df = read_prices(read_ticker, start=start_iso, end=end_iso, db_path=db_path)
        existing_dates = []
        if not df.empty:
            existing_dates = [idx.date().isoformat() for idx in df.index]
    except Exception as exc:
        errors.append(f"read_prices failed: {exc}")
        return {"ok": False, "fetched_ranges": [], "errors": errors, "rows_added": 0}

    # Build full requested date list (calendar days)
    s_date = datetime.fromisoformat(start_iso).date()
    e_date = datetime.fromisoformat(end_iso).date()
    all_dates = [
        (s_date + timedelta(days=i)).isoformat()
        for i in range((e_date - s_date).days + 1)
    ]

    missing = compute_missing_ranges(existing_dates, all_dates)

    # For each missing range, call ingest_pipeline.ingest (adapter will be
    # selected by ingest pipeline). We pass start/end as strings.
    for mr_start, mr_end in missing:
        try:
            res = ingest_pipeline.ingest(
                read_ticker, provider, start=mr_start, end=mr_end
            )
        except Exception as exc:  # defensive
            errors.append(f"ingest failed for {mr_start}..{mr_end}: {exc}")
            continue

        status = res.get("status")
        if status != "success":
            err = res.get("error_message") or "unknown error"
            errors.append(f"ingest error for {mr_start}..{mr_end}: {err}")
        else:
            fetched_ranges.append((mr_start, mr_end))
            # Try to compute rows added: common keys are 'rows_added' or 'rows'
            pers = res.get("persist") or res.get("persist_result") or {}
            rows = pers.get("rows_added") or pers.get("rows") or res.get("rows")
            try:
                rows_added += int(rows) if rows is not None else 0
            except Exception:
                # ignore non-int
                pass

    ok = len(errors) == 0
    return {
        "ok": ok,
        "fetched_ranges": fetched_ranges,
        "errors": errors,
        "rows_added": rows_added,
    }
