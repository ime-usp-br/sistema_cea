import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.models import ApplicationEvent, ServiceApplication
from applications.services import ApplicationSubmissionService
from audits.services import DatasetAuditService
from bank_slips.models import BankSlipPaymentInstrument
from bank_slips.services import BankSlipPaymentService
from payments.models import (
    FeeRequirement,
    ManualPaymentConfirmation,
    PaymentInstrument,
    RefundRequest,
)
from payments.services import (
    APPLICATION_FEE_CONSULTATION,
    APPLICATION_FEE_PROJECT,
    CONSULTATION_TO_PROJECT_CREDIT,
    FeeCalculationService,
    ManualPaymentService,
    ModalityChangeService,
    OverdueBillingService,
    PaymentDomainError,
    PaymentOrchestrationService,
    RefundRequestService,
)
from terms.models import AcademicTerm
from users.models import User


def _file(name: str = "dados.csv", content: bytes = b"coluna_a,coluna_b\n1,2\n") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="text/csv")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-payments-media-"))
class PaymentScenarioTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_pay",
            email="candidate_pay@example.com",
            password="pass",
        )
        self.teacher = User.objects.create_user(
            username="teacher_pay",
            email="teacher_pay@example.com",
            password="pass",
            role=User.Role.TEACHER,
        )
        self.secretariat = User.objects.create_user(
            username="secretariat_pay",
            email="secretariat_pay@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.fee_service = FeeCalculationService()
        self.payment_service = PaymentOrchestrationService()
        self.manual_service = ManualPaymentService()
        self.modality_service = ModalityChangeService()
        self.refund_service = RefundRequestService()
        self.audit_service = DatasetAuditService()

    def create_project(self, owner: User | None = None) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=owner or self.candidate,
            modality="project",
            researcher_name="Maria Projeto",
            contact_email="maria@example.com",
        )

    def create_consultation(self, owner: User | None = None) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=owner or self.candidate,
            modality="consultation",
            researcher_name="João Consulta",
            contact_email="joao@example.com",
        )

    def approve_project_audit(self, application: ServiceApplication) -> None:
        submission = self.audit_service.submit_dataset(
            application=application,
            submitted_by=self.candidate,
            channel="file",
            uploaded_file=_file(),
        )
        self.audit_service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="approved",
        )
        application.refresh_from_db()

    def create_and_pay_application_fee(
        self, application: ServiceApplication
    ) -> PaymentInstrument:
        fee = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        ).first()
        if fee is None:
            fee = self.fee_service.create_application_fee(application)
        assert fee is not None
        instrument = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        self.manual_service.confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        return instrument

    # ------------------------------------------------------------------
    # 8. Taxas e regras financeiras
    # ------------------------------------------------------------------

    def test_TS_FEE_001_taxa_de_projeto_apos_auditoria_aprovada(self) -> None:
        application = self.create_project()
        self.assertEqual(FeeRequirement.objects.filter(application=application).count(), 0)
        self.approve_project_audit(application)
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        self.assertEqual(fee.fee_type, "application_fee")
        self.assertEqual(fee.base_amount, APPLICATION_FEE_PROJECT)
        self.assertEqual(fee.amount, APPLICATION_FEE_PROJECT)

    def test_TS_FEE_002_taxa_de_consulta_na_submissao(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        self.assertEqual(fee.base_amount, APPLICATION_FEE_CONSULTATION)
        self.assertEqual(fee.amount, APPLICATION_FEE_CONSULTATION)

    def test_TS_FEE_003_taxa_de_projeto_sem_credito(self) -> None:
        application = self.create_project()
        self.approve_project_audit(application)
        fee = self.fee_service.create_project_fee(application)
        assert fee is not None
        self.assertEqual(fee.fee_type, "project_fee")
        self.assertEqual(fee.base_amount, Decimal("250.00"))
        self.assertEqual(fee.adjustment_amount, Decimal("0.00"))
        self.assertEqual(fee.amount, Decimal("250.00"))

    def test_TS_FEE_004_taxa_de_projeto_com_credito_de_consulta(self) -> None:
        application = self.create_consultation()
        self.create_and_pay_application_fee(application)
        self.modality_service.convert_to_project(application=application)
        application.refresh_from_db()
        self.assertEqual(application.modality_credit_amount, CONSULTATION_TO_PROJECT_CREDIT)
        fee = self.fee_service.create_project_fee(application)
        assert fee is not None
        self.assertEqual(fee.base_amount, Decimal("250.00"))
        self.assertEqual(fee.adjustment_amount, Decimal("-60.00"))
        self.assertEqual(fee.amount, Decimal("190.00"))

    def test_TS_FEE_005_projeto_pago_aprovado_como_consulta(self) -> None:
        application = self.create_project()
        self.approve_project_audit(application)
        self.create_and_pay_application_fee(application)
        self.modality_service.convert_to_consultation(application=application)
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE)
        self.assertEqual(fee.base_amount, Decimal("60.00"))
        total = application.fee_requirements.aggregate(total=Sum("amount"))["total"]
        self.assertEqual(total, APPLICATION_FEE_CONSULTATION)

    def test_TS_FEE_006_projeto_nao_pago_aprovado_como_consulta(self) -> None:
        application = self.create_project()
        self.approve_project_audit(application)
        self.modality_service.convert_to_consultation(application=application)
        app_fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        self.assertEqual(app_fee.amount, APPLICATION_FEE_CONSULTATION)
        self.assertFalse(
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
            ).exists()
        )

    def test_TS_FEE_007_valor_final_consistente(self) -> None:
        application = self.create_project()
        self.approve_project_audit(application)
        self.fee_service.create_project_fee(application)
        application.refresh_from_db()
        for fee in application.fee_requirements.all():
            self.assertEqual(fee.amount, fee.base_amount + fee.adjustment_amount)

    def test_TS_FEE_008_isencao_de_taxa(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        fee.is_waived = True
        fee.waiver_reason = "Bolsa de estudo"
        fee.save(update_fields=["is_waived", "waiver_reason"])
        fee.refresh_from_db()
        self.assertTrue(fee.is_waived)
        self.assertEqual(fee.waiver_reason, "Bolsa de estudo")

    # ------------------------------------------------------------------
    # 9. Orquestração de pagamento
    # ------------------------------------------------------------------

    def test_TS_PAY_001_candidato_escolhe_pix(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        instrument = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        self.assertEqual(instrument.method, "pix")
        self.assertEqual(instrument.state, PaymentInstrument.State.ACTIVE)
        self.assertEqual(instrument.active_unique_fee_token, fee.pk)

    def test_TS_PAY_002_candidato_escolhe_boleto(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        instrument = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="bank_slip", created_by=self.candidate
        )
        self.assertEqual(instrument.method, "bank_slip")
        self.assertEqual(instrument.state, PaymentInstrument.State.ACTIVE)

    def test_TS_PAY_003_troca_de_pix_para_boleto(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        pix = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        slip = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="bank_slip", created_by=self.candidate
        )
        pix.refresh_from_db()
        self.assertEqual(pix.state, PaymentInstrument.State.SUPERSEDED)
        self.assertIsNone(pix.active_unique_fee_token)
        self.assertEqual(slip.superseded_by_id, None)
        self.assertEqual(slip.state, PaymentInstrument.State.ACTIVE)
        self.assertEqual(
            fee.payment_instruments.filter(state=PaymentInstrument.State.ACTIVE).count(),
            1,
        )

    def test_TS_PAY_004_troca_de_boleto_para_pix(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        slip = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="bank_slip", created_by=self.candidate
        )
        pix = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        slip.refresh_from_db()
        self.assertEqual(slip.state, PaymentInstrument.State.SUPERSEDED)
        self.assertEqual(pix.state, PaymentInstrument.State.ACTIVE)
        self.assertEqual(slip.superseded_by_id, pix.pk)

    def test_TS_PAY_005_um_instrumento_ativo_por_taxa(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PaymentInstrument.objects.create(
                fee_requirement=fee,
                method="pix",
                state=PaymentInstrument.State.ACTIVE,
                amount=fee.amount,
                active_unique_fee_token=fee.pk,
            )

    def test_TS_PAY_006_instrumento_pago_nao_pode_ser_substituido(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        self.create_and_pay_application_fee(application)
        with self.assertRaises(PaymentDomainError):
            self.payment_service.create_payment_instrument(
                fee_requirement=fee, method="pix", created_by=self.candidate
            )

    def test_TS_PAY_007_pix_expirado_permite_nova_geracao(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        expired = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        expired.state = PaymentInstrument.State.EXPIRED
        expired.save(update_fields=["state", "updated_at"])
        new_pix = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        self.assertEqual(new_pix.state, PaymentInstrument.State.ACTIVE)
        self.assertEqual(new_pix.active_unique_fee_token, fee.pk)
        self.assertEqual(
            fee.payment_instruments.filter(state=PaymentInstrument.State.ACTIVE).count(),
            1,
        )

    def test_TS_PAY_008_pagamento_confirmado_libera_fluxo(self) -> None:
        project = self.create_project()
        self.approve_project_audit(project)
        self.create_and_pay_application_fee(project)
        project.refresh_from_db()
        self.assertEqual(
            project.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING,
        )
        consultation = self.create_consultation()
        self.create_and_pay_application_fee(consultation)
        consultation.refresh_from_db()
        self.assertEqual(
            consultation.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
        )

    # ------------------------------------------------------------------
    # 12. Pagamento manual
    # ------------------------------------------------------------------

    def test_TS_MAN_001_confirmacao_manual_de_pagamento(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        instrument = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="manual", created_by=self.secretariat
        )
        confirmation = self.manual_service.confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat, note="Depósito bancário"
        )
        self.assertEqual(confirmation.confirmed_by_id, self.secretariat.pk)
        instrument.refresh_from_db()
        self.assertEqual(instrument.state, PaymentInstrument.State.MANUAL_CONFIRMED)
        self.assertTrue(fee.is_paid)
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=application, event_code="payment.manual_confirmed"
            ).exists()
        )

    def test_TS_MAN_002_pagamento_manual_nao_altera_status_externo(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        instrument = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="manual", created_by=self.secretariat
        )
        self.manual_service.confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        instrument.refresh_from_db()
        self.assertEqual(instrument.state, PaymentInstrument.State.MANUAL_CONFIRMED)

    def test_TS_MAN_003_pagamento_manual_nao_envia_email(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        instrument = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="manual", created_by=self.secretariat
        )
        self.manual_service.confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        email_events = ApplicationEvent.objects.filter(
            application=application, event_code__startswith="notification"
        )
        self.assertEqual(email_events.count(), 0)
        instrument.refresh_from_db()
        self.assertEqual(instrument.state, PaymentInstrument.State.MANUAL_CONFIRMED)

    def test_TS_MAN_004_confirmacao_manual_em_instrumento_pago(self) -> None:
        application = self.create_consultation()
        fee = application.fee_requirements.get(fee_type=FeeRequirement.FeeType.APPLICATION_FEE)
        instrument = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="manual", created_by=self.secretariat
        )
        self.manual_service.confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        before = ManualPaymentConfirmation.objects.count()
        with self.assertRaises(PaymentDomainError):
            self.manual_service.confirm_manual_payment(
                instrument=instrument, confirmed_by=self.secretariat
            )
        self.assertEqual(ManualPaymentConfirmation.objects.count(), before)

    # ------------------------------------------------------------------
    # 13. Reembolso
    # ------------------------------------------------------------------

    def test_TS_REF_001_solicitacao_de_reembolso_apos_rejeicao_paga(self) -> None:
        application = self.create_consultation()
        self.create_and_pay_application_fee(application)
        application.lifecycle_status = ServiceApplication.LifecycleStatus.NOT_APPROVED
        application.save(update_fields=["lifecycle_status", "updated_at"])
        refund = self.refund_service.create_refund_request(
            application=application,
            requested_by=self.secretariat,
            amount=APPLICATION_FEE_CONSULTATION,
            reason="Inscrição rejeitada",
        )
        self.assertEqual(refund.status, RefundRequest.Status.REQUESTED)
        self.assertEqual(refund.amount, APPLICATION_FEE_CONSULTATION)

    def test_TS_REF_002_aprovacao_de_reembolso(self) -> None:
        application = self.create_consultation()
        self.create_and_pay_application_fee(application)
        refund = self.refund_service.create_refund_request(
            application=application,
            requested_by=self.secretariat,
            amount=APPLICATION_FEE_CONSULTATION,
        )
        self.refund_service.approve(
            refund_request=refund, approved_by=self.secretariat
        )
        refund.refresh_from_db()
        self.assertEqual(refund.status, RefundRequest.Status.APPROVED)
        self.assertEqual(refund.approved_by_id, self.secretariat.pk)

    def test_TS_REF_003_execucao_de_reembolso(self) -> None:
        application = self.create_consultation()
        self.create_and_pay_application_fee(application)
        refund = self.refund_service.create_refund_request(
            application=application,
            requested_by=self.secretariat,
            amount=APPLICATION_FEE_CONSULTATION,
        )
        self.refund_service.approve(
            refund_request=refund, approved_by=self.secretariat
        )
        self.refund_service.execute(
            refund_request=refund, executed_by=self.secretariat
        )
        refund.refresh_from_db()
        self.assertEqual(refund.status, RefundRequest.Status.EXECUTED)
        self.assertIsNotNone(refund.executed_at)
        application.refresh_from_db()
        self.assertEqual(
            application.payment_state, ServiceApplication.PaymentState.REFUNDED
        )

    def test_TS_REF_004_conversao_em_vez_de_reembolso(self) -> None:
        application = self.create_project()
        self.approve_project_audit(application)
        self.create_and_pay_application_fee(application)
        refunds_before = RefundRequest.objects.filter(application=application).count()
        self.modality_service.convert_to_consultation(application=application)
        self.assertEqual(
            RefundRequest.objects.filter(application=application).count(),
            refunds_before,
        )
        supplement = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
        )
        self.assertTrue(supplement.exists())

    def test_TS_REF_005_reembolso_nao_pode_exceder_valor_pago(self) -> None:
        application = self.create_consultation()
        self.create_and_pay_application_fee(application)
        with self.assertRaises(PaymentDomainError):
            self.refund_service.create_refund_request(
                application=application,
                requested_by=self.secretariat,
                amount=Decimal("999.00"),
            )
        self.assertEqual(RefundRequest.objects.filter(application=application).count(), 0)

    # ------------------------------------------------------------------
    # 14. Mudança de modalidade
    # ------------------------------------------------------------------

    def test_TS_MOD_001_projeto_nao_pago_convertido_em_consulta(self) -> None:
        application = self.create_project()
        self.approve_project_audit(application)
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        self.payment_service.create_payment_instrument(
            fee_requirement=app_fee, method="pix", created_by=self.candidate
        )
        self.modality_service.convert_to_consultation(application=application)
        application.refresh_from_db()
        self.assertEqual(application.modality, ServiceApplication.Modality.CONSULTATION)
        app_fee.refresh_from_db()
        self.assertEqual(app_fee.amount, APPLICATION_FEE_CONSULTATION)
        for instrument in app_fee.payment_instruments.all():
            self.assertEqual(instrument.state, PaymentInstrument.State.CANCELED)

    def test_TS_MOD_002_projeto_pago_convertido_em_consulta(self) -> None:
        application = self.create_project()
        self.approve_project_audit(application)
        self.create_and_pay_application_fee(application)
        self.modality_service.convert_to_consultation(application=application)
        supplement = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
        )
        self.assertTrue(supplement.exists())
        supplement_fee = supplement.first()
        assert supplement_fee is not None
        self.assertEqual(supplement_fee.amount, Decimal("60.00"))
        self.assertEqual(
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            ).count(),
            1,
        )

    def test_TS_MOD_003_projeto_pago_igual_ou_superior_140(self) -> None:
        application = self.create_consultation()
        self.create_and_pay_application_fee(application)
        self.modality_service.convert_to_project(application=application)
        application.refresh_from_db()
        self.modality_service.convert_to_consultation(application=application)
        self.assertFalse(
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
            ).exists()
        )
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=application, event_code="modality.excess_recorded"
            ).exists()
        )

    def test_TS_MOD_004_consulta_nao_paga_convertida_em_projeto(self) -> None:
        application = self.create_consultation()
        self.modality_service.convert_to_project(application=application)
        application.refresh_from_db()
        self.assertEqual(application.modality, ServiceApplication.Modality.PROJECT)
        self.assertEqual(application.modality_credit_amount, Decimal("0.00"))
        self.assertTrue(application.dataset_audit_required)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.approve_project_audit(application)
        project_app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        self.assertEqual(project_app_fee.amount, APPLICATION_FEE_PROJECT)
        self.assertFalse(
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
            ).exists()
        )

    def test_TS_MOD_005_consulta_paga_convertida_em_projeto(self) -> None:
        application = self.create_consultation()
        self.create_and_pay_application_fee(application)
        self.modality_service.convert_to_project(application=application)
        application.refresh_from_db()
        self.assertEqual(application.modality_credit_amount, CONSULTATION_TO_PROJECT_CREDIT)
        self.approve_project_audit(application)
        project_fee = self.fee_service.create_project_fee(application)
        assert project_fee is not None
        self.assertEqual(project_fee.base_amount, Decimal("250.00"))
        self.assertEqual(project_fee.adjustment_amount, Decimal("-60.00"))
        self.assertEqual(project_fee.amount, Decimal("190.00"))

    # ------------------------------------------------------------------
    # 14b. Regressão: cobrança indevida ao converter Projeto pago -> Consulta
    # ------------------------------------------------------------------

    def test_TS_MOD_006_projeto_com_taxa_de_projeto_paga_convertido_para_consulta_gera_excesso(self) -> None:
        """
        No Laravel, a mudança olhava para a soma de TUDO o que foi pago.
        Se Inscrição (80) + Projeto (250) = 330, e muda para Consulta (140),
        o sistema não deve cobrar R$ 60 extras (Gap 3).
        """
        application = self.create_project()
        self.approve_project_audit(application)

        # Paga taxa de inscrição (80)
        self.create_and_pay_application_fee(application)

        # Cria e Paga taxa de projeto (250)
        project_fee = self.fee_service.create_project_fee(application)
        assert project_fee is not None
        PaymentInstrument.objects.create(
            fee_requirement=project_fee,
            method=PaymentInstrument.Method.PIX,
            state=PaymentInstrument.State.PAID,
            amount=Decimal("250.00"),
        )

        # Converte para Consulta
        self.modality_service.convert_to_consultation(application=application)

        supplement = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
        )
        self.assertFalse(
            supplement.exists(),
            "Não deve gerar taxa complementar de R$ 60,00 se o usuário já pagou R$ 330,00 no total.",
        )

        # Deve ter registrado o evento de excesso
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=application, event_code="modality.excess_recorded"
            ).exists()
        )

    # ------------------------------------------------------------------
    # 14c. Cobrança em massa / inadimplência (OverdueBillingService)
    # ------------------------------------------------------------------

    def test_TS_PAY_010_overdue_billing_service_retorna_boletos_vencidos(self) -> None:
        """Garante que o serviço localiza boletos expirados no passado e ativos localmente."""
        application = self.create_consultation()
        fee = application.fee_requirements.first()
        assert fee is not None

        # Instrumento ATIVO mas vencido há 5 dias no gateway
        instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("140.00"),
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=instrument,
            bank_slip_reference="boleto-vencido-123",
            due_date=timezone.localdate() - timedelta(days=5),
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=Decimal("140.00"),
        )

        service = OverdueBillingService()
        slips = service.get_overdue_slips()

        self.assertEqual(slips.count(), 1)
        self.assertEqual(slips.first().bank_slip_reference, "boleto-vencido-123")

    def test_TS_PAY_010b_overdue_billing_ignora_boletos_pagos_ou_futuros(self) -> None:
        """Só boletos vencidos e ainda ativos entram na lista de inadimplência."""
        application = self.create_consultation()
        fee = application.fee_requirements.first()
        assert fee is not None

        # Pago: não deve constar.
        paid_instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.PAID,
            amount=Decimal("140.00"),
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=paid_instrument,
            bank_slip_reference="boleto-pago",
            due_date=timezone.localdate() - timedelta(days=2),
            bank_status=BankSlipPaymentInstrument.BankStatus.PAID,
            document_amount=Decimal("140.00"),
        )
        # Futuro: não deve constar.
        future_instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("140.00"),
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=future_instrument,
            bank_slip_reference="boleto-futuro",
            due_date=timezone.localdate() + timedelta(days=10),
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=Decimal("140.00"),
        )

        slips = OverdueBillingService().get_overdue_slips()
        references = list(slips.values_list("bank_slip_reference", flat=True))
        self.assertNotIn("boleto-pago", references)
        self.assertNotIn("boleto-futuro", references)

    def test_TS_PAY_011_overdue_billing_view_requer_permissao_secretaria(self) -> None:
        """Garante a View que substitui a rota de inadimplentes no Django."""
        self.client.force_login(self.candidate)
        response = self.client.get(reverse("payments:overdue_list"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("payments:overdue_list"))
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # 14d. Regressão: cancelamento externo no gateway (Gaps A e C)
    # ------------------------------------------------------------------

    def _generate_active_slip(self, fee: FeeRequirement) -> BankSlipPaymentInstrument:
        service = BankSlipPaymentService()
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value={"codigoIDBoleto": "BOL-GAP-001"},
        ):
            return service.generate_bank_slip_for_fee(
                fee_requirement=fee, created_by=self.candidate
            )

    def test_TS_MOD_GAP_001_mudanca_de_modalidade_cancela_boleto_via_soap(self) -> None:
        """Paridade Laravel: converter Projeto -> Consulta baixa o boleto no banco."""
        application = self.create_project()
        self.approve_project_audit(application)
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        slip = self._generate_active_slip(app_fee)

        with patch(
            "bank_slips.gateways.BankSlipGateway.cancelar_boleto"
        ) as mock_cancelar:
            self.modality_service.convert_to_consultation(application=application)
            mock_cancelar.assert_called_once_with(slip.bank_slip_reference)

        slip.refresh_from_db()
        self.assertEqual(
            slip.payment_instrument.state, PaymentInstrument.State.CANCELED
        )

    def test_TS_MOD_GAP_001b_cancelamento_externo_nao_bloqueia_fluxo(self) -> None:
        """Falha no gateway não impede a mudança de modalidade (best-effort)."""
        application = self.create_project()
        self.approve_project_audit(application)
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        slip = self._generate_active_slip(app_fee)

        with patch(
            "bank_slips.gateways.BankSlipGateway.cancelar_boleto",
            side_effect=RuntimeError("SOAP indisponível"),
        ):
            self.modality_service.convert_to_consultation(application=application)

        application.refresh_from_db()
        self.assertEqual(
            application.modality, ServiceApplication.Modality.CONSULTATION
        )
        slip.refresh_from_db()
        self.assertEqual(
            slip.payment_instrument.state, PaymentInstrument.State.CANCELED
        )

    def test_TS_MAN_GAP_001_confirmacao_manual_cancela_boleto_externo(self) -> None:
        """Pagamento manual baixa o boleto/Pix ativo no gateway (anti-duplicidade)."""
        application = self.create_consultation()
        fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        slip = self._generate_active_slip(fee)

        manual = self.payment_service.create_payment_instrument(
            fee_requirement=fee, method="manual", created_by=self.secretariat
        )
        slip.refresh_from_db()
        self.assertEqual(slip.payment_instrument.state, PaymentInstrument.State.SUPERSEDED)

        with patch(
            "bank_slips.gateways.BankSlipGateway.cancelar_boleto"
        ) as mock_cancelar:
            self.manual_service.confirm_manual_payment(
                instrument=manual, confirmed_by=self.secretariat
            )
            mock_cancelar.assert_called_once_with(slip.bank_slip_reference)

        slip.refresh_from_db()
        self.assertEqual(slip.payment_instrument.state, PaymentInstrument.State.CANCELED)
        manual.refresh_from_db()
        self.assertEqual(
            manual.state, PaymentInstrument.State.MANUAL_CONFIRMED
        )
