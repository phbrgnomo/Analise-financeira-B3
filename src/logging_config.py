"""Helpers to configure JSON/structured logging for the project.

Provides a small, dependency-free JSON formatter and a convenience
function `configure_json_logging()` which installs a StreamHandler on
the root logger (or a specific logger) that emits JSON objects.

This is intentionally simple — for production-grade structured logging
prefer `structlog` or configure `logging` with a JSON formatter.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import IO, Optional


class JSONFormatter(logging.Formatter):
    """Minimal JSON formatter for logging.LogRecord objects.

    Emits a compact JSON object with keys: ts, level, logger, message and
    optionally extra fields available on the record.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include pathname/lineno for traceability if present
        try:
            payload["path"] = record.pathname
            payload["lineno"] = record.lineno
        except Exception:
            pass

        # Include any structured data passed via `extra` argument
        # (LogRecord stores extras as attributes on the record)
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord.__dict__ and k not in ("msg", "args")
        }
        if extras:
            # Avoid serializing non-serializable objects; coerce to str
            safe_extras = {
                k: (v if _is_jsonable(v) else str(v)) for k, v in extras.items()
            }
            payload["extra"] = safe_extras

        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            return str(payload)


def _is_jsonable(x) -> bool:
    try:
        json.dumps(x)
        return True
    except Exception:
        return False


def configure_json_logging(
    level: int = logging.INFO,
    logger_name: Optional[str] = None,
    stream: Optional[IO] = None,
) -> None:
    """Configure a JSON stream handler.

    Args:
        level: logging level for the handler (default INFO)
        logger_name: if provided, configure this logger; otherwise configure root logger
        stream: optional output stream (defaults to sys.stderr via StreamHandler)
    """
    tgt_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())

    # Avoid adding multiple handlers if already configured similarly
    # Remove existing StreamHandler handlers to keep output predictable
    existing = [
        h for h in list(tgt_logger.handlers) if isinstance(h, logging.StreamHandler)
    ]
    for h in existing:
        try:
            tgt_logger.removeHandler(h)
        except Exception:
            pass

    tgt_logger.addHandler(handler)
    tgt_logger.setLevel(level)
