"""Testes da tela Cobranças Manuais (Fase 5): seleção em massa e histórico."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from applications.models import ApplicationEvent, ServiceApplication
from applications.services import ApplicationSubmissionService
from bank_slips.models import BankSlipPaymentInstrument
from payments.models import PaymentInstrument
from payments.services import OverdueBillingService
from terms.models import AcademicTerm
from users.models import User


class OverdueBulkSelectionTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.secretariat = User.objects.create_user(
            username="sec",
            email="sec@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.client.force_login(self.secretariat)

    def _make_overdue_slip(
        self,
    ) -> tuple[BankSlipPaymentInstrument, ServiceApplication]:
        owner = User.objects.create_user(
            username=f"cand{User.objects.count()}",
            email=f"cand{User.objects.count()}@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        application = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=owner,
            modality=ServiceApplication.Modality.CONSULTATION,
            researcher_name="Maria",
            contact_email="c@example.com",
        )
        fee = application.fee_requirements.first()
        assert fee is not None
        instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("140.00"),
        )
        slip = BankSlipPaymentInstrument.objects.create(
            payment_instrument=instrument,
            bank_slip_reference=f"REF-{instrument.pk}",
            due_date=date(2000, 1, 1),
            document_amount=Decimal("140.00"),
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
        )
        return slip, application

    # TS-PAY-014 — cobrança em massa apenas dos selecionados
    def test_TS_PAY_014_cobranca_envia_somente_slips_selecionados(self) -> None:
        first, first_application = self._make_overdue_slip()
        second, second_application = self._make_overdue_slip()
        with patch(
            "notifications.services.NotificationService.notify_overdue_reminder"
        ) as notify:
            sent = OverdueBillingService().send_overdue_reminders(
                actor=self.secretariat, slip_ids=[first.pk]
            )
        self.assertEqual(sent, 1)
        notify.assert_called_once()
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=first_application,
                event_code="payment.overdue_reminder_sent",
            ).exists()
        )
        # O segundo boleto vencido não foi cobrado nem gerou evento.
        self.assertFalse(
            ApplicationEvent.objects.filter(
                application=second_application,
                event_code="payment.overdue_reminder_sent",
            ).exists()
        )

    # TS-PAY-014 — a tela exibe checkbox e histórico de cobrança
    def test_TS_PAY_014_view_exibe_checkbox_e_historico(self) -> None:
        slip, _application = self._make_overdue_slip()
        response = self.client.get(reverse("payments:overdue_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{slip.pk}"')
        self.assertContains(response, "Histórico de Cobrança")
        self.assertContains(response, "Enviar e-mail de cobrança para os selecionados")

    # TS-PAY-014 — o POST cobra apenas os boletos marcados
    def test_TS_PAY_014_post_com_slip_ids_dispara_cobranca(self) -> None:
        slip, _application = self._make_overdue_slip()
        with patch(
            "notifications.services.NotificationService.notify_overdue_reminder"
        ) as notify:
            response = self.client.post(
                reverse("payments:overdue_remind"), {"slip_ids": [str(slip.pk)]}
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(notify.call_count, 1)
