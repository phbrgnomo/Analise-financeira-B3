"""Configuração centralizada de logging estruturado para o projeto.

Fornece :class:`JSONFormatter` (saída JSON por linha para ferramentas de
observabilidade) e a função :func:`configure_logging` que configura o handler
raiz com o formatter adequado.  Importe e chame ``configure_logging()`` no
início da aplicação ou da CLI.
"""

import json
import logging
import sys
from datetime import datetime, timezone

# Standard LogRecord attributes to exclude from "extra" fields.
DEFAULT_RECORD_KEYS = {
    "name",
    "msg",
    "message",
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
}

# Substrings considered sensitive; used to redact values in extras.
SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
)


class JSONFormatter(logging.Formatter):
    """Formatador JSON para registros de logging.

    Formata instâncias de `logging.LogRecord` como um objeto JSON compacto.
    Uso principal: serializar `time`, `level`, `logger`, `message` e quaisquer
    campos extras serializáveis. Campos sensíveis com nomes contendo
    substrings como "password", "secret", "token", "api_key" e
    similares são redigidos como "***REDACTED***".

    Métodos notáveis
    -----------------
    - format(record): formata o `LogRecord` e retorna uma string JSON.
    """
    def format(self, record: logging.LogRecord) -> str:
        """Format a LogRecord as a compact JSON string.

        Parameters:
            record (logging.LogRecord): the record to format.

        Returns:
            str: JSON-formatted log string containing time (UTC), level,
            logger, message and any serializable extra fields; sensitive
            keys are redacted.
        """

        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include any structured fields attached to the record (common pattern)
        extra_keys = set(record.__dict__.keys()) - DEFAULT_RECORD_KEYS

        # Redact common sensitive keys to avoid leaking secrets in logs.

        for k in extra_keys:
            try:
                val = record.__dict__[k]
                lowered = str(k).lower()
                if any(substr in lowered for substr in SENSITIVE_KEY_SUBSTRINGS):
                    payload[k] = "***REDACTED***"
                    continue
                json.dumps(val)
                payload[k] = val
            except Exception:
                # Represent non-serializable extras as strings rather than failing
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
