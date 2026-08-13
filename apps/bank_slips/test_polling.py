from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from bank_slips.models import BankSlipPaymentInstrument
from bank_slips.tasks import sync_pending_bank_slips_task
from payments.models import PaymentInstrument
from terms.models import AcademicTerm
from users.models import User


class BankSlipPollingTests(TestCase):
    """Paridade com o cron do legado (Console/Kernel.php): poller de boletos.

    Garante que existe uma task do Celery que varre boletos Emitidos ('E') e
    consulta seus status via SOAP em background, desbloqueando o fluxo quando o
    candidato paga o boleto sem acessar o sistema (TS-BSL-GAP-006).
    """

    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_poll",
            email="candidate_poll@example.com",
            password="pass",
            tax_id="98765432109",
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")

    def create_consultation(self) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            researcher_name="Ana Poll",
            contact_email="ana_poll@example.com",
        )

    def test_TS_BSL_GAP_006_task_de_polling_atualiza_boletos_pendentes(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type="application_fee")

        inst = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("140.00"),
        )
        slip = BankSlipPaymentInstrument.objects.create(
            payment_instrument=inst,
            bank_slip_reference="BOL-PENDENTE-123",
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=Decimal("140.00"),
        )

        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao", return_value="P"
        ):
            synced_count = sync_pending_bank_slips_task()

        self.assertGreaterEqual(synced_count, 1)
        slip.refresh_from_db()
        self.assertEqual(slip.bank_status, BankSlipPaymentInstrument.BankStatus.PAID)
        self.assertEqual(
            slip.payment_instrument.state, PaymentInstrument.State.PAID
        )
        application.refresh_from_db()
        self.assertEqual(
            application.payment_state, ServiceApplication.PaymentState.PAID
        )

    def test_TS_BSL_GAP_006_poller_ignora_boletos_ja_pagos(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type="application_fee")

        inst = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.PAID,
            amount=Decimal("140.00"),
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=inst,
            bank_slip_reference="BOL-PAGO-1",
            bank_status=BankSlipPaymentInstrument.BankStatus.PAID,
            document_amount=Decimal("140.00"),
        )

        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao", return_value="P"
        ) as mock_situacao:
            synced_count = sync_pending_bank_slips_task()

        self.assertEqual(synced_count, 0)
        mock_situacao.assert_not_called()
