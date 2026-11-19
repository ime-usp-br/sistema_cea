"""Expoe a configuração da stack E2E para o teste se auto-verificar.

Garante que a suíte está rodando com gateways simulados, Celery eager e
e-mail em arquivo; se alguém apontar o E2E para a stack de DEV real, o teste
falha imediatamente em vez de fazer chamadas externas silenciosas.
"""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Emite em JSON a configuração relevante da stack E2E."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--json", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        from bank_slips.gateways import get_bank_slip_gateway
        from pix.gateways import get_pix_gateway

        self.stdout.write(
            json.dumps(
                {
                    "debug": settings.DEBUG,
                    "payment_gateway_fake": settings.PAYMENT_GATEWAY_FAKE,
                    "pix_gateway": type(get_pix_gateway()).__name__,
                    "bank_slip_gateway": type(get_bank_slip_gateway()).__name__,
                    "celery_task_always_eager": settings.CELERY_TASK_ALWAYS_EAGER,
                    "email_backend": settings.EMAIL_BACKEND,
                    "email_file_path": settings.EMAIL_FILE_PATH,
                    "media_root": settings.MEDIA_ROOT,
                    "notification_center_email": settings.NOTIFICATION_CENTER_EMAIL,
                }
            )
        )
