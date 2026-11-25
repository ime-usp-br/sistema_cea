"""Formatação de logs estruturados em JSON (TS-NFR-003)."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

SENSITIVE_KEY_RE = re.compile(
    r"(?i)\b(password|senha|token|secret|authorization|api[_-]?key|x-password)\b"
    r"(\s*[:=]\s*)([^\s,;\"']+)"
)
SENSITIVE_FIELDS = {
    "password",
    "senha",
    "token",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "x-password",
}


def redact_sensitive(value: str) -> str:
    """Mascara credenciais em mensagens e exceções antes de ir para o log."""
    return SENSITIVE_KEY_RE.sub(r"\1\2***", value)


class JsonFormatter(logging.Formatter):
    """Serializa registros de log com contexto suficiente para rastreio."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive(record.getMessage()),
        }
        for key in ("application_id", "protocol", "event", "request_id", "user_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        for key in record.__dict__:
            if key.lower() in SENSITIVE_FIELDS:
                payload[key] = "***"
        if record.exc_info:
            payload["exception"] = redact_sensitive(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)
