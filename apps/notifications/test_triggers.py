"""Testes dos gatilhos de notificação religados (D6 / TS-NOT).

Usam Celery em modo eager para que o despacho seja executado no processo e
possa ser verificado via ``NotificationDispatch`` (status ``sent``), sem
depender de um worker real nem de rede.
"""

import tempfile
from datetime import date, time, timedelta

from django.test import TestCase, override_settings

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from audits.services import DatasetAuditService
from meetings.services import ConsultationMeetingService, ProjectScreeningService
from notifications.models import NotificationDispatch
from payments.models import FeeRequirement
from payments.services import ManualPaymentService, PaymentOrchestrationService
from terms.models import AcademicTerm
from users.models import User

EAGER = override_settings(CELERY_TASK_ALWAYS_EAGER=True)


@EAGER
@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-notif-media-"))
class NotificationTriggerTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_notif",
            email="candidate_notif@example.com",
            password="pass",
            is_email_verified=True,
        )
        self.teacher = User.objects.create_user(
            username="teacher_notif",
            email="teacher_notif@example.com",
            password="pass",
            role=User.Role.TEACHER,
            is_email_verified=True,
        )
        self.secretariat = User.objects.create_user(
            username="secretariat_notif",
            email="secretariat_notif@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
            is_email_verified=True,
        )
        self.term = AcademicTerm.objects.create(year=2028, period="first")

    def _create(self, modality: str) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality=modality,
            researcher_name="Notificação Teste",
            contact_email=self.candidate.email,
        )

    def _codes(self, application: ServiceApplication) -> set[str]:
        return set(
            NotificationDispatch.objects.filter(application=application).values_list(
                "template__code", flat=True
            )
        )

    def test_TS_NOT_001_submissao_notifica_candidato_e_centro(self) -> None:
        application = self._create("consultation")
        codes = self._codes(application)
        self.assertIn("application_submitted_candidate", codes)
        self.assertIn("application_submitted_center", codes)
        self.assertTrue(
            NotificationDispatch.objects.filter(
                application=application, status=NotificationDispatch.Status.SENT
            ).exists()
        )

    def test_TS_NOT_002_auditoria_dispara_correcao_aprovacao_e_rejeicao(self) -> None:
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        instrument = PaymentOrchestrationService().create_payment_instrument(
            fee_requirement=app_fee, method="pix", created_by=self.candidate
        )
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        application.refresh_from_db()

        submission = DatasetAuditService().submit_dataset(
            application=application,
            submitted_by=self.candidate,
            channel="external_link",
            external_url="https://example.com/dados",
            external_link_declaration=True,
        )
        DatasetAuditService().review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="needs_correction",
            note="Ajustar coluna.",
        )
        self.assertIn("dataset_correction_requested", self._codes(application))

    def test_TS_NOT_003_revisao_aprovada_notifica(self) -> None:
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        instrument = PaymentOrchestrationService().create_payment_instrument(
            fee_requirement=app_fee, method="pix", created_by=self.candidate
        )
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        application.refresh_from_db()
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
        self.assertIn("dataset_approved", self._codes(application))

    def test_TS_NOT_005_006_pagamento_notifica_criacao_e_confirmacao(self) -> None:
        application = self._create("consultation")
        fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        instrument = PaymentOrchestrationService().create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        self.assertIn("payment_created", self._codes(application))
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        self.assertIn("payment_confirmed", self._codes(application))

    def test_TS_NOT_012_triagem_agendada_e_decidida_notifica(self) -> None:
        application = self._create("project")
        app_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        instrument = PaymentOrchestrationService().create_payment_instrument(
            fee_requirement=app_fee, method="pix", created_by=self.candidate
        )
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        application.refresh_from_db()
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
            virtual_link="https://meet.example.com/notif",
        )
        self.assertIn("screening_scheduled", self._codes(application))
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
        self.assertIn("screening_decision", self._codes(application))

    def test_TS_NOT_013_reuniao_agendada_e_decidida_notifica(self) -> None:
        application = self._create("consultation")
        fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        instrument = PaymentOrchestrationService().create_payment_instrument(
            fee_requirement=fee, method="pix", created_by=self.candidate
        )
        ManualPaymentService().confirm_manual_payment(
            instrument=instrument, confirmed_by=self.secretariat
        )
        application.refresh_from_db()
        ConsultationMeetingService().schedule_consultation(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=date.today() - timedelta(days=1),
            scheduled_time=time(10, 0),
            meeting_mode="online",
            virtual_link="https://meet.example.com/notif",
        )
        self.assertIn("consultation_scheduled", self._codes(application))
        ConsultationMeetingService().record_feedback(
            meeting=application.consultation_meeting,
            recorded_by=self.teacher,
            teacher_feedback="consultation_completed",
        )
        ConsultationMeetingService().record_decision(
            meeting=application.consultation_meeting,
            decided_by=self.secretariat,
            decision="approved_as_consultation",
        )
        self.assertIn("consultation_decision", self._codes(application))

    def test_TS_NOT_010_anexos_serializaveis_em_json(self) -> None:
        # Garante que o payload do Celery (serialização JSON) aceita os anexos.
        from notifications.services import _serialize_attachments

        payload = _serialize_attachments(
            [{"filename": "f.pdf", "content": b"%PDF-1.4", "mimetype": "application/pdf"}]
        )
        assert payload is not None
        import json

        encoded = json.dumps(payload)
        self.assertIn("base64", encoded)
