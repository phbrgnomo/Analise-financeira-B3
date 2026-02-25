from datetime import datetime, timezone


def now_utc_iso() -> str:
    """Return current UTC datetime as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def to_iso_date(d) -> str:
    """Normalize date/datetime/str to YYYY-MM-DD string."""
    if d is None:
        return None
    if isinstance(d, str):
        return d
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    raise TypeError("Unsupported date type for to_iso_date")
