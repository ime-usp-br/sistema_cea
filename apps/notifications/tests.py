import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from applications.models import ApplicationEvent, ServiceApplication
from bank_slips.services import BankSlipPaymentService
from files.services import create_file_asset_from_bytes
from notifications.models import NotificationDispatch, NotificationTemplate
from notifications.services import NotificationService
from notifications.tasks import send_notification_task
from payments.models import FeeRequirement, PaymentInstrument
from payments.services import ManualPaymentService, ModalityChangeService
from terms.models import AcademicTerm
from users.models import User

EAGER = override_settings(CELERY_TASK_ALWAYS_EAGER=True)


class NotificationScenarioTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate1",
            email="candidate@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.secretariat = User.objects.create_user(
            username="secretariat1",
            email="secretariat@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            protocol="123456789",
            modality=ServiceApplication.Modality.PROJECT,
            researcher_name="Maria Pesquisadora",
            contact_email="candidate@example.com",
        )
        self.service = NotificationService()

    def _fee_and_instrument(
        self, method: str = PaymentInstrument.Method.PIX, state: str = PaymentInstrument.State.ACTIVE
    ) -> tuple[FeeRequirement, PaymentInstrument]:
        fee = FeeRequirement.objects.create(
            application=self.application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=Decimal("80.00"),
            adjustment_amount=Decimal("0.00"),
            amount=Decimal("80.00"),
            reason="Taxa de inscrição",
        )
        instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=method,
            state=state,
            amount=Decimal("80.00"),
        )
        return fee, instrument

    # TS-NOT-001
    @EAGER
    def test_TS_NOT_001_inscricao_submetida_notifica_candidato_e_equipe(self) -> None:
        self.service.notify_application_submitted(self.application)
        emails = {d.template.code for d in NotificationDispatch.objects.all()}
        self.assertEqual(
            emails,
            {"application_submitted_candidate", "application_submitted_center"},
        )
        self.assertEqual(len(mail.outbox), 2)
        candidate = NotificationDispatch.objects.get(
            template__code="application_submitted_candidate"
        )
        self.assertEqual(candidate.status, NotificationDispatch.Status.SENT)
        self.assertEqual(candidate.recipient_email, "candidate@example.com")
        self.assertIsNotNone(candidate.sent_at)

    # TS-NOT-002
    @EAGER
    def test_TS_NOT_002_correcao_solicitada_notifica_candidato(self) -> None:
        self.service.notify_correction_requested(
            self.application, note="Preencha o campo de contexto."
        )
        dispatch = NotificationDispatch.objects.get()
        self.assertEqual(dispatch.template.code, "dataset_correction_requested")
        self.assertEqual(dispatch.status, NotificationDispatch.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Preencha o campo de contexto.", mail.outbox[0].body)

    # TS-NOT-003
    @EAGER
    def test_TS_NOT_003_auditoria_aprovada_notifica_candidato(self) -> None:
        self.service.notify_dataset_approved(self.application)
        dispatch = NotificationDispatch.objects.get()
        self.assertEqual(dispatch.template.code, "dataset_approved")
        self.assertEqual(dispatch.status, NotificationDispatch.Status.SENT)

    # TS-NOT-004
    @EAGER
    def test_TS_NOT_004_auditoria_rejeitada_notifica_candidato_e_secretaria(self) -> None:
        self.service.notify_dataset_rejected(self.application, note="Motivo")
        codes = {d.template.code for d in NotificationDispatch.objects.all()}
        self.assertEqual(
            codes,
            {"dataset_rejected", "dataset_rejected_secretariat"},
        )
        self.assertEqual(len(mail.outbox), 2)

    # TS-NOT-005
    @EAGER
    def test_TS_NOT_005_cobranca_criada_notifica_candidato(self) -> None:
        _, instrument = self._fee_and_instrument()
        self.service.notify_payment_created(self.application, instrument)
        dispatch = NotificationDispatch.objects.get()
        self.assertEqual(dispatch.template.code, "payment_created")
        self.assertEqual(dispatch.status, NotificationDispatch.Status.SENT)

    # TS-NOT-006
    @EAGER
    def test_TS_NOT_006_pagamento_pix_notifica_candidato(self) -> None:
        _, instrument = self._fee_and_instrument(method=PaymentInstrument.Method.PIX)
        self.service.notify_payment_confirmed(self.application, instrument)
        dispatch = NotificationDispatch.objects.get()
        self.assertEqual(dispatch.template.code, "payment_confirmed")
        self.assertEqual(dispatch.status, NotificationDispatch.Status.SENT)

    # TS-NOT-007
    @EAGER
    def test_TS_NOT_007_pagamento_boleto_notifica_candidato(self) -> None:
        _, instrument = self._fee_and_instrument(
            method=PaymentInstrument.Method.BANK_SLIP
        )
        self.service.notify_payment_confirmed(self.application, instrument)
        dispatch = NotificationDispatch.objects.get()
        self.assertEqual(dispatch.template.code, "payment_confirmed")
        self.assertEqual(dispatch.status, NotificationDispatch.Status.SENT)

    # TS-NOT-008
    def test_TS_NOT_008_pagamento_manual_nao_notifica_candidato(self) -> None:
        _, instrument = self._fee_and_instrument(
            method=PaymentInstrument.Method.MANUAL
        )
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument,
            confirmed_by=self.secretariat,
            note="Confirmado por depósito.",
        )
        self.assertEqual(NotificationDispatch.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=self.application, event_code="payment.manual_confirmed"
            ).exists()
        )

    # TS-NOT-009
    @EAGER
    def test_TS_NOT_009_template_inativo_nao_envia(self) -> None:
        NotificationTemplate.objects.filter(code="dataset_approved").update(
            is_active=False
        )
        self.service.notify_dataset_approved(self.application)
        self.assertEqual(NotificationDispatch.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    # TS-NOT-010
    @EAGER
    @patch("django.core.mail.EmailMessage.send", side_effect=RuntimeError("SMTP down"))
    def test_TS_NOT_010_falha_de_envio_marca_failed(self, _mock_send) -> None:
        _, instrument = self._fee_and_instrument()
        self.service.notify_payment_confirmed(self.application, instrument)
        dispatch = NotificationDispatch.objects.get()
        self.assertEqual(dispatch.status, NotificationDispatch.Status.FAILED)
        self.assertIn("SMTP down", dispatch.error_message or "")

    # TS-NOT-010 (task direta sem template -> retorna None sem despacho)
    def test_TS_NOT_010_task_sem_template_nao_cria_despacho(self) -> None:
        result = send_notification_task(
            "template_inexistente",
            "x@example.com",
            {},
            self.application.pk,
        )
        self.assertIsNone(result)
        self.assertEqual(NotificationDispatch.objects.count(), 0)

    # TS-NOT-012 — anexos suportados via EmailMessage (paridade com attachData do legado)
    @EAGER
    def test_TS_NOT_012_anexo_de_boleto_pdf_chega_ao_email(self) -> None:
        NotificationTemplate.objects.update_or_create(
            code="payment_slip_regenerated",
            defaults={
                "name": "Boleto regenerado",
                "audience": NotificationTemplate.Audience.CANDIDATE,
                "subject": "Seu boleto foi reemitido",
                "body": "Olá {{ candidate_name }}.",
                "is_active": True,
            },
        )
        dispatch = send_notification_task(
            "payment_slip_regenerated",
            "candidate@example.com",
            {"candidate_name": "Maria"},
            self.application.pk,
            attachments=[
                {
                    "filename": "boleto-123.pdf",
                    "content": b"%PDF-1.4 dummy",
                    "mimetype": "application/pdf",
                }
            ],
        )
        self.assertIsNotNone(dispatch)
        self.assertEqual(dispatch.status, NotificationDispatch.Status.SENT)
        email = mail.outbox[-1]
        self.assertEqual(len(email.attachments), 1)
        name, content, mimetype = email.attachments[0]
        self.assertEqual(name, "boleto-123.pdf")
        self.assertEqual(content, b"%PDF-1.4 dummy")
        self.assertEqual(mimetype, "application/pdf")

    # TS-NOT-GAP-001 — Paridade Laravel: e-mail de mudança de modalidade anexa o boleto.
    @EAGER
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-notif-media-"))
    def test_TS_NOT_GAP_001_mudanca_de_modalidade_anexa_novo_boleto_ao_email(self) -> None:
        fee = FeeRequirement.objects.create(
            application=self.application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=Decimal("80.00"),
            adjustment_amount=Decimal("0.00"),
            amount=Decimal("80.00"),
            reason="Taxa de inscrição",
        )
        slip_service = BankSlipPaymentService()
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value={"codigoIDBoleto": "BOL-NOT-GAP"},
        ):
            slip = slip_service.generate_bank_slip_for_fee(
                fee_requirement=fee, created_by=self.candidate
            )
        asset = create_file_asset_from_bytes(
            application=self.application,
            uploaded_by=self.candidate,
            content=b"%PDF-1.4 novo boleto",
            filename="boleto-BOL-NOT-GAP.pdf",
            content_type="application/pdf",
            purpose="bank_slip_pdf",
        )
        slip.pdf_asset = asset
        slip.save(update_fields=["pdf_asset", "updated_at"])

        with patch("bank_slips.gateways.BankSlipGateway.cancelar_boleto"):
            ModalityChangeService().convert_to_consultation(
                application=self.application
            )

        emails = mail.outbox
        self.assertGreater(len(emails), 0)
        email = emails[-1]
        self.assertEqual(
            email.subject,
            f"Sua inscrição {self.application.protocol} foi alterada para Consulta",
        )
        self.assertEqual(
            len(email.attachments), 1, "O PDF do novo boleto não foi anexado ao e-mail."
        )
        name, _content, mimetype = email.attachments[0]
        self.assertEqual(name, "boleto-BOL-NOT-GAP.pdf")
        self.assertEqual(mimetype, "application/pdf")
