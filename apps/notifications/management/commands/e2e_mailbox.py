"""Lê a caixa de e-mail em disco usada pela stack E2E.

A stack E2E configura ``EMAIL_BACKEND`` para o backend de arquivo e
``CELERY_TASK_ALWAYS_EAGER=True``; assim cada notificação vira um arquivo em
``settings.EMAIL_FILE_PATH`` sem SMTP. Este comando expõe as mensagens em JSON
para que os testes consigam extrair links (confirmação de e-mail, reset de
senha) — o "desvio" do e-mail para a caixa de teste.

Uso:
    manage.py e2e_mailbox --to candidato@example.com --latest --json
"""

from __future__ import annotations

import json
import os
from email import message_from_binary_file
from email.message import Message
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _message_body(message: Message) -> str:
    """Extrai o corpo texto (preferindo text/plain) de uma mensagem."""
    if not message.is_multipart():
        payload = message.get_payload(decode=True)
        if not isinstance(payload, (bytes, bytearray)):
            return str(payload or "")
        charset = message.get_content_charset() or "utf-8"
        return bytes(payload).decode(charset, errors="replace")
    for part in message.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            payload = part.get_payload(decode=True)
            if not isinstance(payload, (bytes, bytearray)):
                continue
            charset = part.get_content_charset() or "utf-8"
            return bytes(payload).decode(charset, errors="replace")
    return ""


class Command(BaseCommand):
    help = "Lista as mensagens da caixa E2E em disco (backend filebased)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--to", default=None, help="Filtra pelo destinatário.")
        parser.add_argument(
            "--subject-contains",
            default=None,
            help="Filtra por trecho do assunto.",
        )
        parser.add_argument(
            "--latest",
            action="store_true",
            help="Devolve apenas a mensagem mais recente.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emite JSON (padrão: resumo legível).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("e2e_mailbox só está disponível com DEBUG=True.")
        if "filebased" not in settings.EMAIL_BACKEND:
            raise CommandError(
                "e2e_mailbox exige EMAIL_BACKEND=filebased "
                f"(atual: {settings.EMAIL_BACKEND})."
            )
        mailbox = Path(settings.EMAIL_FILE_PATH or "")
        if not mailbox.is_dir():
            self._output([], options)
            return

        wanted_to = (options["to"] or "").strip().lower()
        wanted_subject = (options["subject_contains"] or "").strip().lower()
        messages: list[dict[str, Any]] = []
        for path in sorted(
            (entry for entry in mailbox.iterdir() if entry.is_file()),
            key=lambda item: item.stat().st_mtime,
        ):
            with path.open("rb") as handle:
                message = message_from_binary_file(handle)
            to_header = str(message.get("To", ""))
            recipient = parseaddr(to_header)[1].strip().lower()
            subject = str(message.get("Subject", ""))
            if wanted_to and wanted_to not in (recipient, to_header.lower()):
                continue
            if wanted_subject and wanted_subject not in subject.lower():
                continue
            messages.append(
                {
                    "file": os.path.basename(path),
                    "to": recipient,
                    "to_header": to_header,
                    "from": str(message.get("From", "")),
                    "subject": subject,
                    "body": _message_body(message),
                    "mtime": path.stat().st_mtime,
                }
            )
        if options["latest"] and messages:
            messages = messages[-1:]
        self._output(messages, options)

    def _output(self, messages: list[dict[str, Any]], options: dict[str, Any]) -> None:
        if options["json"]:
            self.stdout.write(json.dumps(messages, ensure_ascii=False))
            return
        if not messages:
            self.stdout.write(self.style.WARNING("Nenhuma mensagem encontrada."))
            return
        for message in messages:
            self.stdout.write(
                f"{message['to']} | {message['subject']} | {message['file']}"
            )
