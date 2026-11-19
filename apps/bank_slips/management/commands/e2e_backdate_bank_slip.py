"""Recua o vencimento de um boleto para exercitar cobrança manual no E2E.

A confirmação manual e a tela de inadimplência exigem boleto vencido. O
gateway simulado emite boletos com vencimento no futuro, portanto este comando
(apenas com ``DEBUG=True``) ajusta a data no banco de teste.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Define o vencimento de um boleto E2E para ontem (somente DEBUG)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--protocol", required=True, help="Protocolo da inscrição.")
        parser.add_argument(
            "--fee-type",
            default="application_fee",
            help="Tipo da taxa cujo boleto será recuado.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from bank_slips.models import BankSlipPaymentInstrument

        if not settings.DEBUG:
            raise CommandError("e2e_backdate_bank_slip exige DEBUG=True.")
        slip = (
            BankSlipPaymentInstrument.objects.select_related(
                "payment_instrument__fee_requirement__application"
            )
            .filter(
                payment_instrument__fee_requirement__application__protocol=options[
                    "protocol"
                ],
                payment_instrument__fee_requirement__fee_type=options["fee_type"],
            )
            .order_by("-created_at")
            .first()
        )
        if slip is None:
            raise CommandError(
                f"Nenhum boleto de {options['fee_type']} para "
                f"{options['protocol']}."
            )
        slip.due_date = timezone.localdate() - timedelta(days=1)
        slip.save(update_fields=["due_date", "updated_at"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Boleto {slip.pk} de {options['protocol']} vence em {slip.due_date}."
            )
        )
