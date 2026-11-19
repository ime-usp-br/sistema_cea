"""Cria uma inscrição importada sem dono para o E2E de resgate (somente DEBUG)."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria uma inscrição legada sem dono para testar o fluxo de resgate."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--protocol", required=True)
        parser.add_argument("--contact-email", required=True)
        parser.add_argument(
            "--modality",
            default="project",
            choices=["project", "consultation"],
        )
        parser.add_argument("--researcher-name", default="Pesquisador Legado E2E")

    def handle(self, *args: Any, **options: Any) -> None:
        from applications.models import ServiceApplication
        from terms.models import AcademicTerm

        if not settings.DEBUG:
            raise CommandError("e2e_create_imported_application exige DEBUG=True.")
        term = AcademicTerm.current()
        if term is None:
            raise CommandError("Nenhum período letivo cadastrado.")
        application, created = ServiceApplication.objects.get_or_create(
            protocol=options["protocol"],
            defaults={
                "term": term,
                "owner": None,
                "modality": options["modality"],
                "origin": ServiceApplication.Origin.IMPORTED,
                "lifecycle_status": ServiceApplication.LifecycleStatus.SUBMITTED,
                "researcher_name": options["researcher_name"],
                "contact_email": options["contact_email"],
                "legacy_contact_email": options["contact_email"],
            },
        )
        self.stdout.write(
            json.dumps(
                {
                    "protocol": application.protocol,
                    "created": created,
                    "owner": application.owner_id,
                    "term": term.pk,
                }
            )
        )
