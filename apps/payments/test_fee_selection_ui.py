"""Testes da UI de pagamento por taxa (D3 / TS-PAY).

Cobrem a seleção de taxa pendente pela área do candidato, o pagamento da Taxa
de Projeto e do Complemento de Taxa, a restrição de propriedade e a
imutabilidade de taxa já paga.
"""

import base64
import tempfile
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from audits.services import DatasetAuditService
from meetings.services import ProjectScreeningService
from payments.models import FeeRequirement, PaymentInstrument
from payments.services import (
    ManualPaymentService,
    PaymentOrchestrationService,
    advance_lifecycle_after_application_fee,
)
from pix.services import PixPaymentService
from terms.models import AcademicTerm
from users.models import User

PIX_RESULT = {
    "idfpix": "pix-ui-0001",
    "qrCode": "00020126580014br.gov.bcb.pix0136ui000000",
    "qrCodeImgBase64": base64.b64encode(b"png").decode(),
    "status": "ativo",
}


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-fee-ui-media-"), DEBUG=True)
class FeeSelectionUITests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_ui",
            email="candidate_ui@example.com",
            password="pass",
            is_email_verified=True,
        )
        self.other = User.objects.create_user(
            username="candidate_ui_other",
            email="candidate_ui_other@example.com",
            password="pass",
            is_email_verified=True,
        )
        self.teacher = User.objects.create_user(
            username="teacher_ui",
            email="teacher_ui@example.com",
            password="pass",
            role=User.Role.TEACHER,
            is_email_verified=True,
        )
        self.secretariat = User.objects.create_user(
            username="secretariat_ui",
            email="secretariat_ui@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
            is_email_verified=True,
        )
        self.term = AcademicTerm.objects.create(year=2027, period="first")
        self.client.force_login(self.candidate)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create(self, modality: str, owner: User | None = None) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=owner or self.candidate,
            modality=modality,
            researcher_name="Pesquisador UI",
            contact_email="ui@example.com",
        )

    def _pay_fee(self, application: ServiceApplication, fee: FeeRequirement) -> None:
        instrument = PaymentOrchestrationService().create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        application.refresh_from_db()

    def _project_awaiting_project_fee(self) -> ServiceApplication:
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        self._pay_fee(application, app_fee)
        submission = DatasetAuditService().submit_dataset(
            application=application,
            submitted_by=self.candidate,
            channel="external_link",
            external_url="https://example.com/dados",
            external_link_declaration=True,
        )
        DatasetAuditService().review_submission(
            submission=submission, reviewer=self.teacher, outcome="approved"
        )
        application.refresh_from_db()
        ProjectScreeningService().schedule_screening(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=date.today() - timedelta(days=1),
            scheduled_time=time(10, 0),
            meeting_mode="online",
            virtual_link="https://meet.example.com/ui",
        )
        ProjectScreeningService().record_feedback(
            screening=application.project_screening,
            recorded_by=self.teacher,
            teacher_feedback="screening_completed",
        )
        ProjectScreeningService().record_decision(
            screening=application.project_screening,
            decided_by=self.secretariat,
            decision="approved_as_project",
        )
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )
        return application

    # ------------------------------------------------------------------
    # D3 — seleção e pagamento de qualquer taxa
    # ------------------------------------------------------------------

    def test_TS_PAY_UI_001_projeto_paga_taxa_de_projeto_pela_ui(self) -> None:
        application = self._project_awaiting_project_fee()
        project_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.PROJECT_FEE
        )
        url = reverse("payments:fee_payment", args=[application.protocol])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["fee"].pk, project_fee.pk)
        self.assertContains(response, "Taxa de Projeto")

        with patch("pix.gateways.PixGateway.generate_pix", return_value=PIX_RESULT):
            response = self.client.post(
                url, {"method": "pix", "fee_id": project_fee.pk}
            )
        self.assertEqual(response.status_code, 302)
        instrument = PaymentInstrument.objects.get(
            fee_requirement=project_fee,
            state=PaymentInstrument.State.ACTIVE,
        )
        self.assertEqual(instrument.method, PaymentInstrument.Method.PIX)

        # Confirma o pagamento e valida a transição da jornada.
        PixPaymentService().simulate_payment(instrument.pix_instrument)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT,
        )

    def test_TS_PAY_UI_002_taxa_pendente_e_a_selecionada_por_padrao(self) -> None:
        application = self._project_awaiting_project_fee()
        project_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.PROJECT_FEE
        )
        response = self.client.get(
            reverse("payments:fee_payment", args=[application.protocol])
        )
        self.assertEqual(response.context["fee"].pk, project_fee.pk)

    def test_TS_PAY_UI_003_nao_permite_pagar_taxa_de_outra_inscricao(self) -> None:
        own = self._create("project")
        foreign = self._create("project", owner=self.other)
        foreign_fee = foreign.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        url = reverse("payments:fee_payment", args=[own.protocol])
        with patch("pix.gateways.PixGateway.generate_pix", return_value=PIX_RESULT):
            response = self.client.post(
                url, {"method": "pix", "fee_id": foreign_fee.pk}
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            PaymentInstrument.objects.filter(fee_requirement=foreign_fee).exists()
        )

    def test_TS_PAY_UI_004_taxa_paga_nao_reabre(self) -> None:
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        self._pay_fee(application, app_fee)
        url = reverse("payments:fee_payment", args=[application.protocol])
        response = self.client.get(f"{url}?fee={app_fee.pk}")
        self.assertContains(response, "Taxa paga.")
        response = self.client.post(
            url, {"method": "pix", "fee_id": app_fee.pk}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            PaymentInstrument.objects.filter(fee_requirement=app_fee).count(), 1
        )

    def test_TS_PAY_UI_005_paga_complemento_de_taxa_na_consulta(self) -> None:
        # Projeto pago convertido em Consulta gera o complemento de R$ 60.
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        self._pay_fee(application, app_fee)
        from payments.services import ModalityChangeService

        ModalityChangeService().convert_to_consultation(
            application=application, decided_by=self.secretariat
        )
        application.refresh_from_db()
        supplement = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
        )
        self.assertEqual(supplement.amount, Decimal("60.00"))
        url = reverse("payments:fee_payment", args=[application.protocol])
        with patch("bank_slips.gateways.BankSlipGateway.gerar_boleto") as gerar:
            gerar.return_value = {"codigoIDBoleto": "boleto-ui-1"}
            response = self.client.post(
                url, {"method": "bank_slip", "fee_id": supplement.pk}
            )
        self.assertEqual(response.status_code, 302)
        instrument = PaymentInstrument.objects.get(fee_requirement=supplement)
        from bank_slips.services import BankSlipPaymentService

        BankSlipPaymentService().simulate_payment(instrument.bank_slip_instrument)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
        )

    def test_TS_PAY_UI_006_advance_nao_aprova_com_taxa_de_projeto_pendente(self) -> None:
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        self._pay_fee(application, app_fee)
        from payments.services import FeeCalculationService

        FeeCalculationService().create_project_fee(application)
        application.lifecycle_status = ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
        application.save(update_fields=["lifecycle_status", "updated_at"])
        advance_lifecycle_after_application_fee(application)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )

    def test_TS_REF_001_candidato_solicita_reembolso_e_volta_a_ficha(self) -> None:
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        self._pay_fee(application, app_fee)
        response = self.client.post(
            reverse("payments:refund_create", args=[application.protocol]),
            {"amount": "80.00", "reason": "Desistência."},
        )
        self.assertRedirects(
            response,
            reverse("applications:detail", args=[application.protocol]),
        )
        self.assertTrue(
            application.refund_requests.filter(
                status="requested"
            ).exists()
        )
