"""Cleanup dos dados criados pela suíte E2E (T3.1).

A suíte roda contra o banco de desenvolvimento; para não acumular inscrições
entre execuções, os protocolos criados são marcados com exclusão lógica
(``soft_deleted_at``), preservando a retenção exigida pelo sistema.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Marca como excluídas (soft delete) as inscrições E2E informadas por protocolo."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--protocol",
            action="append",
            default=[],
            dest="protocols",
            help="Protocolo de uma inscrição criada pelo E2E (pode repetir).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from applications.models import ServiceApplication

        protocols: list[str] = options["protocols"]
        if not protocols:
            self.stdout.write(
                self.style.WARNING("Nenhum protocolo informado; nada a limpar.")
            )
            return
        queryset = ServiceApplication.all_objects.filter(
            protocol__in=protocols, soft_deleted_at__isnull=True
        )
        updated = queryset.update(
            soft_deleted_at=timezone.now(), updated_at=timezone.now()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{updated} inscrição(ões) E2E marcada(s) como excluída(s)."
            )
        )
