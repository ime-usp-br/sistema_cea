from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SendTestEmailCommandTests(TestCase):
    def test_envia_para_destinatario_informado(self) -> None:
        call_command(
            "send_test_email",
            to="destino@example.com",
            subject="Assunto de teste",
            body="Corpo de teste",
        )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["destino@example.com"])
        self.assertEqual(message.subject, "Assunto de teste")
        self.assertEqual(message.body, "Corpo de teste")
        self.assertEqual(message.from_email, settings.DEFAULT_FROM_EMAIL)

    @override_settings(
        MAIL_DEV_TEST="dev@example.com",
        NOTIFICATION_CENTER_EMAIL="centro@example.com",
    )
    def test_usa_mail_dev_test_quando_to_nao_e_informado(self) -> None:
        call_command("send_test_email")
        self.assertEqual(mail.outbox[0].to, ["dev@example.com"])

    @override_settings(
        MAIL_DEV_TEST="",
        NOTIFICATION_CENTER_EMAIL="centro@example.com",
    )
    def test_usa_notification_center_como_ultimo_fallback(self) -> None:
        call_command("send_test_email")
        self.assertEqual(mail.outbox[0].to, ["centro@example.com"])

    def test_falha_de_smtp_vira_command_error(self) -> None:
        with (
            patch(
                "notifications.management.commands.send_test_email.send_mail",
                side_effect=RuntimeError("SMTP down"),
            ),
            self.assertRaises(CommandError),
        ):
            call_command("send_test_email", to="destino@example.com")

        self.assertEqual(len(mail.outbox), 0)
