"""Testes E2E/integração das Jornadas Pix/Boleto (Consulta) e Auditoria (Projeto).

Estes testes percorrem o fluxo HTTP completo (Client do Django + Service Layer),
simulando apenas os gateways externos de Pix (REST) e Boleto (SOAP). Cada cenário
valida não só a resposta HTTP, mas também os efeitos colaterais no banco:
lifecycle_status, payment_state, taxa criada e eventos de auditoria.

Referências de cenários: TEST_SCENARIOS.md (TS-PAY, TS-PIX, TS-BSL, TS-AUD).
"""

from __future__ import annotations

import base64
import tempfile
from decimal import Decimal
from typing import Any
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.factories import build_valid_form_payload
from applications.models import ServiceApplication
from bank_slips.models import BankSlipPaymentInstrument
from pix.models import PixPaymentInstrument
from pix.services import PixPaymentService
from terms.factories import AcademicTermFactory
from users.factories import SecretariatFactory, TeacherFactory, UserFactory

_PDF_BYTES = b"%PDF-1.4 mock boleto content"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode("ascii")

# Contrato WSPIX (docs/PIX.md): /pix/gerar retorna idfpix, qrCode e qrCodeImgBase64.
PIX_RESULT = {
    "idfpix": "pix-jornada-001",
    "qrCode": "00020126580014br.gov.bcb.pix0136jornada-000000",
    "qrCodeImgBase64": base64.b64encode(b"png-jornada").decode("ascii"),
    "status": "ativo",
    "expiracao": 3600,
}

# Contrato WS-Boleto (docs/BOLETO.md): gerarBoletoRegistrado retorna somente
# codigoIDBoleto; o PDF vem de obterBoleto (campo boletoPDF).
SLIP_RESULT = {
    "codigoIDBoleto": "boleto-jornada-001",
    "valorDesconto": None,
}


def _csv_file(name: str = "dados.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name, b"coluna_a,coluna_b\n1,2\n", content_type="text/csv"
    )


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-journey-media-"),
    PIX_WEBHOOK_TOKEN="teste-token",
)
class PixBoletoConsultationJourneyTests(TestCase):
    """Jornada 1: Inscrição de Consulta com pagamento via Pix ou Boleto."""

    def setUp(self) -> None:
        self.term = AcademicTermFactory()
        self.candidate = UserFactory()
        self.client.force_login(self.candidate)

    def _create_consultation_form(self) -> ServiceApplication:
        payload = build_valid_form_payload(
            modality=ServiceApplication.Modality.CONSULTATION,
            term_pk=self.term.pk,
        )
        response = self.client.post(reverse("applications:create"), payload)
        self.assertEqual(response.status_code, 302)
        return ServiceApplication.objects.get(
            owner=self.candidate,
            modality=ServiceApplication.Modality.CONSULTATION,
        )

    def _choose_method(self, application: ServiceApplication, method: str) -> None:
        response = self.client.post(
            reverse("payments:fee_payment", args=[application.protocol]),
            {"method": method},
        )
        self.assertEqual(response.status_code, 302)

    def _generate_pix(self, application: ServiceApplication) -> None:
        with patch("pix.gateways.PixGateway.generate_pix", return_value=PIX_RESULT):
            response = self.client.post(
                reverse("pix:generate", args=[application.protocol])
            )
        self.assertEqual(response.status_code, 302)

    # ------------------------------------------------------------------
    # Escolha de método de pagamento em /pagamento/inscricao/<protocolo>/
    # ------------------------------------------------------------------

    def test_TS_PAY_001_pagina_de_pagamento_exibe_taxa_e_aceita_pix(self) -> None:
        application = self._create_consultation_form()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )

        response = self.client.get(
            reverse("payments:fee_payment", args=[application.protocol])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["application"], application)
        self.assertEqual(response.context["fee"].amount, Decimal("140.00"))

        self._choose_method(application, "pix")
        instrument = application.fee_requirements.first().payment_instruments.get()
        self.assertEqual(instrument.method, "pix")
        self.assertEqual(instrument.state, "active")
        self.assertIsNotNone(instrument.active_unique_fee_token)

    def test_TS_PAY_002_pagina_de_pagamento_aceita_boleto(self) -> None:
        application = self._create_consultation_form()
        self._choose_method(application, "bank_slip")
        instrument = application.fee_requirements.first().payment_instruments.get()
        self.assertEqual(instrument.method, "bank_slip")
        self.assertEqual(instrument.state, "active")

    # ------------------------------------------------------------------
    # Pix: contrato de payload documentado em ARCHITECTURE.md §21.4
    # ------------------------------------------------------------------

    def test_TS_PIX_001_jornada_payload_respeita_contrato(self) -> None:
        application = self._create_consultation_form()
        self._choose_method(application, "pix")

        captured: dict[str, Any] = {}

        def fake_generate(payload: dict[str, Any]) -> dict[str, Any]:
            captured.update(payload)
            return PIX_RESULT

        with patch("pix.gateways.PixGateway.generate_pix", side_effect=fake_generate):
            self.client.post(reverse("pix:generate", args=[application.protocol]))

        self.assertEqual(captured["valor"], "140,00")  # formato pt-BR
        self.assertEqual(captured["expiracao"], settings.PIX_EXPIRATION_SECONDS)
        self.assertEqual(captured["tipoPessoa"], "PF")
        self.assertEqual(
            captured["codigoFonteRecurso"], settings.PIX_CODIGO_FONTE_RECURSO
        )
        self.assertEqual(
            captured["codigoUnidadeDespesa"], settings.PIX_CODIGO_UNIDADE_DESPESA
        )
        self.assertEqual(captured["estruturaHierarquica"], settings.PIX_ESTRUTURA_HIERARQUICA)
        self.assertIn("infoCobranca", captured)
        self.assertEqual(captured["docPesOrg"].isdigit(), True)

    # ------------------------------------------------------------------
    # Pix: simulação de pagamento -> awaiting_consultation_scheduling
    # ------------------------------------------------------------------

    def test_TS_PIX_jornada_pix_webhook_avanca_para_agendamento(self) -> None:
        application = self._create_consultation_form()
        self._choose_method(application, "pix")
        self._generate_pix(application)

        response = self.client.get(
            reverse("pix:detail", args=[application.protocol])
        )
        self.assertEqual(response.status_code, 200)

        pix = PixPaymentInstrument.objects.get()
        self.assertEqual(pix.payment_instrument.state, "active")

        response = self.client.post(
            "/webhooks/pix/",
            data={
                "idfpix": pix.pix_reference,
                "status": "Pago",
                "valor": "140,00",
            },
            content_type="application/json",
            HTTP_X_TOKEN="teste-token",
        )
        self.assertEqual(response.status_code, 200)

        application.refresh_from_db()
        self.assertEqual(application.payment_state, ServiceApplication.PaymentState.PAID)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
        )
        self.assertTrue(application.events.filter(event_code="pix.confirmed").exists())

    def test_TS_PIX_010_jornada_pix_simulacao_servico_avanca_fluxo(self) -> None:
        application = self._create_consultation_form()
        self._choose_method(application, "pix")
        self._generate_pix(application)
        pix = PixPaymentInstrument.objects.get()

        with override_settings(DEBUG=True):
            PixPaymentService().simulate_payment(pix)

        application.refresh_from_db()
        self.assertEqual(application.payment_state, ServiceApplication.PaymentState.PAID)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
        )

    # ------------------------------------------------------------------
    # Boleto: contrato de payload documentado em ARCHITECTURE.md §22.5
    # ------------------------------------------------------------------

    def test_TS_BSL_001_jornada_payload_respeita_contrato(self) -> None:
        application = self._create_consultation_form()
        self._choose_method(application, "bank_slip")

        captured: dict[str, Any] = {}

        def fake_gerar(payload: dict[str, Any]) -> dict[str, Any]:
            captured.update(payload)
            return SLIP_RESULT

        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            side_effect=fake_gerar,
        ):
            self.client.post(reverse("bank_slips:generate", args=[application.protocol]))

        self.assertEqual(captured["valorDocumento"], "140.00")  # com ponto
        day, month, year = captured["dataVencimentoBoleto"].split("/")
        self.assertEqual(len(day), 2)
        self.assertEqual(len(month), 2)
        self.assertEqual(len(year), 4)
        self.assertEqual(captured["tipoSacado"], "PF")
        self.assertEqual(captured["cpfCnpj"].isdigit(), True)
        self.assertIn("instrucoesObjetoCobranca", captured)
        self.assertIn("codigoUnidadeDespesa", captured)
        self.assertIn("codigoFonteRecurso", captured)
        self.assertIn("estruturaHierarquica", captured)

    # ------------------------------------------------------------------
    # Boleto: geração + download do PDF em /boleto/<id>/pdf/
    # ------------------------------------------------------------------

    def test_TS_BSL_jornada_boleto_gera_e_baixa_pdf(self) -> None:
        application = self._create_consultation_form()
        self._choose_method(application, "bank_slip")

        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value=SLIP_RESULT,
        ):
            response = self.client.post(
                reverse("bank_slips:generate", args=[application.protocol])
            )
        self.assertEqual(response.status_code, 302)

        slip = BankSlipPaymentInstrument.objects.get()
        self.assertEqual(slip.bank_slip_reference, "boleto-jornada-001")
        self.assertEqual(slip.bank_status, "E")

        response = self.client.get(
            reverse("bank_slips:detail", args=[application.protocol])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["slip"], slip)

        # O PDF é obtido sob demanda via obterBoleto (docs/BOLETO.md), campo boletoPDF.
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_boleto_pdf",
            return_value=_PDF_B64,
        ):
            response = self.client.get(
                reverse("bank_slips:download_pdf", args=[slip.pk])
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-audit-media-"))
class AuditProjectJourneyTests(TestCase):
    """Jornada 2: Inscrição de Projeto submetida à auditoria docente."""

    def setUp(self) -> None:
        self.term = AcademicTermFactory()
        self.candidate = UserFactory()
        self.teacher = TeacherFactory()
        self.secretariat = SecretariatFactory()

    def _create_project_form(self) -> ServiceApplication:
        payload = build_valid_form_payload(
            modality=ServiceApplication.Modality.PROJECT,
            term_pk=self.term.pk,
        )
        self.client.force_login(self.candidate)
        response = self.client.post(reverse("applications:create"), payload)
        self.assertEqual(response.status_code, 302)
        return ServiceApplication.objects.get(
            owner=self.candidate,
            modality=ServiceApplication.Modality.PROJECT,
        )

    def _submit_file(self, application: ServiceApplication) -> None:
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("audits:submit", args=[application.protocol]),
            {"channel": "file", "file": _csv_file()},
        )
        self.assertEqual(response.status_code, 302)

    # ------------------------------------------------------------------
    # Criação de Projeto + envio de dados (arquivo e link)
    # ------------------------------------------------------------------

    def test_TS_AUD_jornada_projeto_comeca_aguardando_envio(self) -> None:
        application = self._create_project_form()
        self.assertTrue(application.dataset_audit_required)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.assertFalse(application.fee_requirements.exists())

    def test_TS_AUD_003_jornada_envio_por_arquivo_e_fila_docente(self) -> None:
        application = self._create_project_form()

        response = self.client.get(
            reverse("audits:submit", args=[application.protocol])
        )
        self.assertEqual(response.status_code, 200)

        self._submit_file(application)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW,
        )

        submission = application.audit_submissions.get()
        self.assertEqual(submission.submission_channel, "file")
        self.assertIsNotNone(submission.file_asset_id)
        self.assertIsNone(submission.external_url)

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("audits:teacher_queue"))
        self.assertEqual(response.status_code, 200)
        submissions = response.context["submissions"]
        self.assertIn(submission.pk, [s.pk for s in submissions])

    def test_TS_AUD_005_jornada_envio_por_link_externo(self) -> None:
        application = self._create_project_form()
        self.client.force_login(self.candidate)

        response = self.client.post(
            reverse("audits:submit", args=[application.protocol]),
            {
                "channel": "external_link",
                "external_url": "https://drive.example.com/dados",
                "external_link_declaration": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        submission = application.audit_submissions.get()
        self.assertEqual(submission.submission_channel, "external_link")
        self.assertEqual(submission.external_url, "https://drive.example.com/dados")
        self.assertTrue(submission.external_link_declaration)
        self.assertIsNone(submission.file_asset_id)

        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW,
        )

    # ------------------------------------------------------------------
    # Revisão docente: correção, aprovação e rejeição
    # ------------------------------------------------------------------

    def test_TS_AUD_009_jornada_docente_solicita_correcao(self) -> None:
        application = self._create_project_form()
        self._submit_file(application)
        submission = application.audit_submissions.get()

        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("audits:review", args=[submission.pk]),
            {"outcome": "needs_correction", "note": "Reenvie com a coluna de datas."},
        )
        self.assertEqual(response.status_code, 302)

        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_CORRECTION,
        )
        submission.refresh_from_db()
        self.assertEqual(submission.state, "needs_correction")
        self.assertEqual(submission.reviews.get().outcome, "needs_correction")

    def test_TS_AUD_011_jornada_docente_aprova_cria_taxa_80(self) -> None:
        application = self._create_project_form()
        self._submit_file(application)
        submission = application.audit_submissions.get()

        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("audits:review", args=[submission.pk]),
            {"outcome": "approved"},
        )
        self.assertEqual(response.status_code, 302)

        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )
        submission.refresh_from_db()
        self.assertEqual(submission.state, "approved")

        fee = application.fee_requirements.get(fee_type="application_fee")
        self.assertEqual(fee.base_amount, Decimal("80.00"))
        self.assertEqual(fee.amount, Decimal("80.00"))

    def test_TS_AUD_012_jornada_docente_rejeita_para_secretaria(self) -> None:
        application = self._create_project_form()
        self._submit_file(application)
        submission = application.audit_submissions.get()

        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("audits:review", args=[submission.pk]),
            {"outcome": "rejected", "note": "Dados insuficientes."},
        )
        self.assertEqual(response.status_code, 302)

        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.DATASET_REJECTED_PENDING_RESOLUTION,
        )
        submission.refresh_from_db()
        self.assertEqual(submission.state, "rejected")

        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("audits:resolution_list"))
        self.assertEqual(response.status_code, 200)
        submissions = response.context["submissions"]
        self.assertIn(submission.pk, [s.pk for s in submissions])
