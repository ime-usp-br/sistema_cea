"""Testes de logs estruturados (TS-NFR-003)."""

from __future__ import annotations

import json
import logging

from core.logging import JsonFormatter
from django.conf import settings
from django.test import SimpleTestCase


class StructuredLoggingTests(SimpleTestCase):
    def test_TS_NFR_003_formatter_emite_json_com_contexto(self) -> None:
        record = logging.LogRecord(
            name="applications.services",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Falha ao processar",
            args=(),
            exc_info=None,
        )
        record.application_id = 42
        record.protocol = "123456789"
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["level"], "ERROR")
        self.assertEqual(payload["logger"], "applications.services")
        self.assertEqual(payload["message"], "Falha ao processar")
        self.assertEqual(payload["application_id"], 42)
        self.assertEqual(payload["protocol"], "123456789")
        self.assertIn("timestamp", payload)

    def test_TS_NFR_003_logging_configurado_com_formatter_json(self) -> None:
        self.assertEqual(
            settings.LOGGING["formatters"]["json"]["()"],
            "core.logging.JsonFormatter",
        )
        self.assertEqual(settings.LOGGING["handlers"]["console"]["formatter"], "json")
