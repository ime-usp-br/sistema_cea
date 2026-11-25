"""Teste da sincronização SOAP/Pix por linha no relatório (D7 opcional)."""

import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import ServiceApplication
from bank_slips.models import BankSlipPaymentInstrument
from payments.models import FeeRequirement, PaymentInstrument
from pix.models import PixPaymentInstrument
from reports.services import ReportService
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

    def test_TS_REP_003_sincroniza_boleto_pago(self) -> None:
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

    def test_TS_REP_002_sincroniza_pix_concluido(self) -> None:
        self.instrument.method = PaymentInstrument.Method.PIX
        self.instrument.state = PaymentInstrument.State.ACTIVE
        self.instrument.save(update_fields=["method", "state", "updated_at"])
        self.slip.delete()
        pix = PixPaymentInstrument.objects.create(
            payment_instrument=self.instrument,
            pix_reference="SYNC-PIX-1",
            qr_code_payload="00020126sync",
        )
        with patch(
            "pix.gateways.PixGateway.check_pix_status",
            return_value={"status": "Concluído", "valor": "140,00"},
        ):
            synced = ReportService().sync_application_payments(self.application)
        self.assertEqual(synced, {"bank_slips": 0, "pix": 1})
        self.instrument.refresh_from_db()
        pix.refresh_from_db()
        self.assertEqual(self.instrument.state, PaymentInstrument.State.PAID)
        self.assertEqual((pix.external_status or "").lower(), "pago")

    def test_TS_REP_002_candidato_nao_sincroniza(self) -> None:
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("reports:financial_sync", args=[self.application.protocol])
        )
        self.assertEqual(response.status_code, 403)
