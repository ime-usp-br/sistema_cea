"""Testes da rota só-DEBUG de simulação de pagamento (T6 / E2E)."""

import base64
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.models import User

PIX_RESULT = {
    "idfpix": "pix-sim-view-1",
    "qrCode": "00020126580014br.gov.bcb.pix0136simview",
    "qrCodeImgBase64": base64.b64encode(b"png").decode(),
    "status": "ativo",
}


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-sim-media-"), DEBUG=True)
class SimulatePaymentViewTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="sim_candidate",
            email="sim_candidate@example.com",
            password="pass",
            is_email_verified=True,
        )
        self.other = User.objects.create_user(
            username="sim_other",
            email="sim_other@example.com",
            password="pass",
            is_email_verified=True,
        )
        self.term = AcademicTerm.objects.create(year=2029, period="first")
        self.application = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            researcher_name="Simulação",
            contact_email=self.candidate.email,
        )
        self.fee = self.application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )

    def _create_pix(self) -> PaymentInstrument:
        from pix.services import PixPaymentService

        with patch("pix.gateways.PixGateway.generate_pix", return_value=PIX_RESULT):
            PixPaymentService().generate_pix_for_fee(
                fee_requirement=self.fee, created_by=self.candidate
            )
        return PaymentInstrument.objects.get(
            fee_requirement=self.fee, method=PaymentInstrument.Method.PIX
        )

    def test_TS_PAY_SIM_001_confirmar_pix_em_dev(self) -> None:
        instrument = self._create_pix()
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("payments:simulate_payment", args=[instrument.pk])
        )
        self.assertEqual(response.status_code, 302)
        instrument.refresh_from_db()
        self.assertEqual(instrument.state, PaymentInstrument.State.PAID)
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
        )

    @override_settings(DEBUG=False)
    def test_TS_PAY_SIM_002_rota_indisponivel_sem_debug(self) -> None:
        instrument = self._create_pix()
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("payments:simulate_payment", args=[instrument.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_TS_PAY_SIM_003_nao_simula_pagamento_de_terceiros(self) -> None:
        instrument = self._create_pix()
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("payments:simulate_payment", args=[instrument.pk])
        )
        self.assertEqual(response.status_code, 403)
        instrument.refresh_from_db()
        self.assertNotEqual(instrument.state, PaymentInstrument.State.PAID)

    def test_TS_PAY_SIM_004_metodo_manual_nao_simulavel(self) -> None:
        instrument = PaymentInstrument.objects.create(
            fee_requirement=self.fee,
            method=PaymentInstrument.Method.MANUAL,
            state=PaymentInstrument.State.ACTIVE,
            amount=self.fee.amount,
        )
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("payments:simulate_payment", args=[instrument.pk])
        )
        self.assertEqual(response.status_code, 404)
