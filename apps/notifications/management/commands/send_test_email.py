from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Envia um e-mail de teste usando a configuração SMTP atual. "
        "Útil para validar MAIL_* no ambiente de homologação."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--to",
            default=None,
            help=(
                "Destinatário do teste. Se omitido, usa MAIL_DEV_TEST e depois "
                "NOTIFICATION_CENTER_EMAIL."
            ),
        )
        parser.add_argument(
            "--subject",
            default="[TESTE] Inscrições CEA - envio de e-mail",
            help="Assunto da mensagem de teste.",
        )
        parser.add_argument(
            "--body",
            default=(
                "Este é um e-mail de teste enviado pelo sistema de inscrições "
                "do CEA. Se você recebeu esta mensagem, a configuração SMTP "
                "está funcionando."
            ),
            help="Corpo da mensagem de teste.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        recipient = (
            options["to"]
            or settings.MAIL_DEV_TEST
            or settings.NOTIFICATION_CENTER_EMAIL
        )
        if not recipient:
            raise CommandError(
                "Informe --to ou configure MAIL_DEV_TEST/NOTIFICATION_CENTER_EMAIL."
            )

        self.stdout.write(f"Backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(
            "Servidor: "
            f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT} "
            f"(TLS={settings.EMAIL_USE_TLS}, SSL={settings.EMAIL_USE_SSL})"
        )
        self.stdout.write(f"Remetente: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Destinatário: {recipient}")

        try:
            sent = send_mail(
                subject=options["subject"],
                message=options["body"],
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception as exc:  # noqa: BLE001 - reporta qualquer falha de SMTP
            raise CommandError(f"Falha ao enviar e-mail: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(f"E-mail enviado ({sent} mensagem(ns)).")
        )
