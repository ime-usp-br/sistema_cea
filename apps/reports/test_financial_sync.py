"""Teste da sincronização SOAP/Pix por linha no relatório (D7 opcional)."""

import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import ServiceApplication
from bank_slips.models import BankSlipPaymentInstrument
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.models import User


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-report-sync-"))
class FinancialReportSyncTests(TestCase):
    def setUp(self) -> None:
        self.secretariat = User.objects.create_user(
            username="sec_sync",
            email="sec_sync@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
            is_email_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="cand_sync",
            email="cand_sync@example.com",
            password="pass",
            is_email_verified=True,
        )
        self.term = AcademicTerm.objects.create(year=2031, period="first")
        self.application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            modality=ServiceApplication.Modality.CONSULTATION,
            protocol="321321321",
            researcher_name="Sync Financeiro",
            contact_email=self.candidate.email,
        )
        self.fee = FeeRequirement.objects.create(
            application=self.application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=Decimal("140.00"),
            amount=Decimal("140.00"),
        )
        self.instrument = PaymentInstrument.objects.create(
            fee_requirement=self.fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=self.fee.amount,
        )
        self.slip = BankSlipPaymentInstrument.objects.create(
            payment_instrument=self.instrument,
            bank_slip_reference="SYNC-1",
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=self.fee.amount,
        )

    def test_TS_REP_002_sincroniza_boleto_pago(self) -> None:
        self.client.force_login(self.secretariat)
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao", return_value="P"
        ):
            response = self.client.post(
                reverse("reports:financial_sync", args=[self.application.protocol])
            )
        self.assertEqual(response.status_code, 200)
        self.instrument.refresh_from_db()
        self.assertEqual(self.instrument.state, PaymentInstrument.State.PAID)

    def test_TS_REP_002_candidato_nao_sincroniza(self) -> None:
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("reports:financial_sync", args=[self.application.protocol])
        )
        self.assertEqual(response.status_code, 403)
