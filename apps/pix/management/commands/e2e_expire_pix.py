"""Expira o Pix ativo de uma inscrição para os testes E2E (TS-PAY-007)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Marca como expirado o Pix ativo da inscrição (somente DEBUG)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--protocol", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        from payments.models import PaymentInstrument
        from pix.models import PixPaymentInstrument

        if not settings.DEBUG:
            raise CommandError("e2e_expire_pix exige DEBUG=True.")

        instruments = PaymentInstrument.objects.filter(
            fee_requirement__application__protocol=options["protocol"],
            method=PaymentInstrument.Method.PIX,
            state=PaymentInstrument.State.ACTIVE,
        ).select_related("pix_instrument")
        count = 0
        now = timezone.now()
        for instrument in instruments:
            instrument.state = PaymentInstrument.State.EXPIRED
            instrument.active_unique_fee_token = None
            instrument.save(
                update_fields=["state", "active_unique_fee_token", "updated_at"]
            )
            pix = getattr(instrument, "pix_instrument", None)
            if pix is not None:
                PixPaymentInstrument.objects.filter(pk=pix.pk).update(
                    external_status="expired",
                    expires_at=now - timedelta(minutes=1),
                    updated_at=now,
                )
            count += 1

        self.stdout.write(json.dumps({"expired": count}))
