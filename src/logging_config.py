import json
import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include any structured fields attached to the record (common pattern)
        extra_keys = set(record.__dict__.keys()) - set(
            [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            ]
        )
        for k in extra_keys:
            try:
                json.dumps(record.__dict__[k])
                payload[k] = record.__dict__[k]
            except Exception:
                # ignore non-serializable extras
                payload[k] = str(record.__dict__[k])

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger to emit compact JSON logs to stdout.

    This is intentionally lightweight and avoids extra runtime dependencies.
    """
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    # Remove existing handlers to avoid duplicate output in tests/environments
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)
    root.addHandler(handler)
