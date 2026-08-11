from datetime import date, time
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from applications.models import ServiceApplication
from meetings.models import ConsultationMeeting, ProjectScreening
from meetings.services import (
    ConsultationMeetingService,
    MeetingDomainError,
    ProjectScreeningService,
)
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.models import User

FUTURE_DATE = date(2099, 1, 1)
FUTURE_TIME = time(10, 0)
PAST_DATE = date(2000, 1, 1)
PAST_TIME = time(0, 0)


class MeetingScenarioTests(TestCase):
    def setUp(self) -> None:
        self.teacher = User.objects.create_user(
            username="teacher1",
            email="teacher1@example.com",
            password="pass",
            role=User.Role.TEACHER,
        )
        self.secretariat = User.objects.create_user(
            username="secretariat1",
            email="secretariat1@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.screening_service = ProjectScreeningService()
        self.consultation_service = ConsultationMeetingService()

    def _application(
        self,
        *,
        modality: str,
        lifecycle_status: str,
        protocol: str,
        owner: User | None = None,
        credit: Decimal | None = None,
    ) -> ServiceApplication:
        return ServiceApplication.objects.create(
            term=self.term,
            owner=owner or self.teacher,
            protocol=protocol,
            modality=modality,
            lifecycle_status=lifecycle_status,
            modality_credit_amount=credit or Decimal("0.00"),
            researcher_name="Maria Pesquisadora",
            contact_email="maria@example.com",
        )

    def project_awaiting_scheduling(self, **kwargs) -> ServiceApplication:
        return self._application(
            modality="project",
            lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING,
            protocol="111000111",
            **kwargs,
        )

    def consultation_awaiting_scheduling(self, **kwargs) -> ServiceApplication:
        return self._application(
            modality="consultation",
            lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
            protocol="222000222",
            **kwargs,
        )

    def make_paid_app_fee(self, application: ServiceApplication, amount: Decimal) -> FeeRequirement:
        fee = FeeRequirement.objects.create(
            application=application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=amount,
            adjustment_amount=Decimal("0.00"),
            amount=amount,
            reason="Taxa de inscrição",
        )
        PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.MANUAL,
            state=PaymentInstrument.State.PAID,
            amount=amount,
            paid_at=self.term.created_at,
        )
        return fee

    def schedule_project(self, application: ServiceApplication, **kwargs) -> ProjectScreening:
        return self.screening_service.schedule_screening(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=kwargs.get("scheduled_date", FUTURE_DATE),
            scheduled_time=kwargs.get("scheduled_time", FUTURE_TIME),
            meeting_mode=kwargs.get("meeting_mode", "online"),
            virtual_link=kwargs.get("virtual_link", "https://meet.example.com/sala"),
            place=kwargs.get("place"),
        )

    def schedule_consultation(self, application: ServiceApplication, **kwargs) -> ConsultationMeeting:
        return self.consultation_service.schedule_consultation(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=kwargs.get("scheduled_date", FUTURE_DATE),
            scheduled_time=kwargs.get("scheduled_time", FUTURE_TIME),
            meeting_mode=kwargs.get("meeting_mode", "online"),
            virtual_link=kwargs.get("virtual_link", "https://meet.example.com/sala"),
            place=kwargs.get("place"),
        )

    # TS-MEET-001
    def test_TS_MEET_001_agendar_triagem_para_projeto(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        self.assertEqual(ProjectScreening.objects.count(), 1)
        self.assertEqual(screening.application_id, application.pk)
        self.assertEqual(screening.state, ProjectScreening.State.SCHEDULED)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_RESULT,
        )
        self.assertTrue(
            application.events.filter(event_code="meeting.screening_scheduled").exists()
        )

    # TS-MEET-002
    def test_TS_MEET_002_bloquear_triagem_para_consulta(self) -> None:
        application = self.consultation_awaiting_scheduling()
        with self.assertRaises(MeetingDomainError):
            self.schedule_project(application)
        self.assertEqual(ProjectScreening.objects.count(), 0)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
        )

    # TS-MEET-003
    def test_TS_MEET_003_agendar_reuniao_para_consulta(self) -> None:
        application = self.consultation_awaiting_scheduling()
        meeting = self.schedule_consultation(application)
        self.assertEqual(ConsultationMeeting.objects.count(), 1)
        self.assertEqual(meeting.application_id, application.pk)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_RESULT,
        )
        self.assertTrue(
            application.events.filter(
                event_code="meeting.consultation_scheduled"
            ).exists()
        )

    # TS-MEET-004
    def test_TS_MEET_004_bloquear_reuniao_para_projeto(self) -> None:
        application = self.project_awaiting_scheduling()
        with self.assertRaises(MeetingDomainError):
            self.schedule_consultation(application)
        self.assertEqual(ConsultationMeeting.objects.count(), 0)

    # TS-MEET-005
    def test_TS_MEET_005_reuniao_online_exige_link(self) -> None:
        application = self.project_awaiting_scheduling()
        with self.assertRaises(MeetingDomainError):
            self.schedule_project(application, meeting_mode="online", virtual_link=None)
        self.assertEqual(ProjectScreening.objects.count(), 0)

        # Verifica a constraint no banco.
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectScreening.objects.create(
                application=application,
                scheduled_date=FUTURE_DATE,
                scheduled_time=FUTURE_TIME,
                meeting_mode="online",
                virtual_link=None,
                place=None,
            )

    # TS-MEET-006
    def test_TS_MEET_006_reuniao_presencial_exige_local(self) -> None:
        application = self.consultation_awaiting_scheduling()
        with self.assertRaises(MeetingDomainError):
            self.schedule_consultation(application, meeting_mode="in_person", place=None)
        self.assertEqual(ConsultationMeeting.objects.count(), 0)

        with self.assertRaises(IntegrityError), transaction.atomic():
            ConsultationMeeting.objects.create(
                application=application,
                scheduled_date=FUTURE_DATE,
                scheduled_time=FUTURE_TIME,
                meeting_mode="in_person",
                virtual_link=None,
                place=None,
            )

    # TS-MEET-007
    def test_TS_MEET_007_reagendar(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        rescheduled = self.screening_service.reschedule_screening(
            screening=screening,
            rescheduled_by=self.secretariat,
            scheduled_date=date(2099, 2, 1),
            scheduled_time=time(14, 30),
        )
        rescheduled.refresh_from_db()
        self.assertEqual(rescheduled.scheduled_date, date(2099, 2, 1))
        self.assertEqual(rescheduled.scheduled_time, time(14, 30))
        self.assertEqual(rescheduled.state, ProjectScreening.State.RESCHEDULED)
        self.assertTrue(
            application.events.filter(
                event_code="meeting.screening_rescheduled"
            ).exists()
        )

    # TS-MEET-008
    def test_TS_MEET_008_cancelar(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        self.screening_service.cancel_screening(
            screening=screening,
            canceled_by=self.secretariat,
        )
        screening.refresh_from_db()
        self.assertEqual(screening.state, ProjectScreening.State.CANCELED)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING,
        )
        self.assertTrue(
            application.events.filter(event_code="meeting.screening_canceled").exists()
        )

    # TS-MEET-009
    def test_TS_MEET_009_decisao_aprovado_como_projeto(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        screening = self.screening_service.record_decision(
            screening=screening,
            decided_by=self.teacher,
            decision="approved_as_project",
            decision_note="Aprovado",
        )
        screening.refresh_from_db()
        self.assertEqual(screening.decision, "approved_as_project")
        self.assertEqual(screening.state, ProjectScreening.State.COMPLETED)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT,
        )
        project_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.PROJECT_FEE
        )
        self.assertEqual(project_fee.amount, Decimal("250.00"))

    def test_TS_MEET_009b_decisao_aprovado_como_projeto_com_credito(self) -> None:
        application = self.project_awaiting_scheduling(credit=Decimal("60.00"))
        screening = self.schedule_project(application)
        self.screening_service.record_decision(
            screening=screening,
            decided_by=self.teacher,
            decision="approved_as_project",
        )
        application.refresh_from_db()
        project_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.PROJECT_FEE
        )
        self.assertEqual(project_fee.base_amount, Decimal("250.00"))
        self.assertEqual(project_fee.amount, Decimal("190.00"))

    # TS-MEET-010
    def test_TS_MEET_010_decisao_aprovado_como_consulta(self) -> None:
        application = self.project_awaiting_scheduling()
        self.make_paid_app_fee(application, Decimal("80.00"))
        screening = self.schedule_project(application)
        self.screening_service.record_decision(
            screening=screening,
            decided_by=self.teacher,
            decision="approved_as_consultation",
        )
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_CONSULTATION,
        )
        self.assertEqual(application.modality, ServiceApplication.Modality.CONSULTATION)
        supplement = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
        )
        self.assertEqual(supplement.amount, Decimal("60.00"))
        self.assertFalse(
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.PROJECT_FEE
            ).exists()
        )

    # TS-MEET-011
    def test_TS_MEET_011_decisao_nao_aprovado(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        self.screening_service.record_decision(
            screening=screening,
            decided_by=self.teacher,
            decision="not_approved",
        )
        screening.refresh_from_db()
        self.assertEqual(screening.decision, "not_approved")
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.NOT_APPROVED,
        )
        self.assertEqual(application.fee_requirements.count(), 0)

    def test_TS_MEET_011b_reuniao_decisao_nao_aprovado(self) -> None:
        application = self.consultation_awaiting_scheduling()
        meeting = self.schedule_consultation(application)
        self.consultation_service.record_decision(
            meeting=meeting,
            decided_by=self.teacher,
            decision="not_approved",
        )
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.NOT_APPROVED,
        )

    # TS-MEET-012
    def test_TS_MEET_012_feedback_docente_apos_evento(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.screening_service.schedule_screening(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=PAST_DATE,
            scheduled_time=PAST_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/passado",
        )
        screening = self.screening_service.record_feedback(
            screening=screening,
            recorded_by=self.teacher,
            teacher_feedback="screening_completed",
        )
        screening.refresh_from_db()
        self.assertEqual(
            screening.teacher_feedback,
            ProjectScreening.TeacherFeedback.SCREENING_COMPLETED,
        )

    def test_TS_MEET_012b_feedback_bloqueado_antes_do_evento(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        with self.assertRaises(MeetingDomainError):
            self.screening_service.record_feedback(
                screening=screening,
                recorded_by=self.teacher,
                teacher_feedback="screening_completed",
            )
        screening.refresh_from_db()
        self.assertIsNone(screening.teacher_feedback)

    def test_TS_MEET_012c_feedback_bloqueado_antes_do_evento_consulta(self) -> None:
        application = self.consultation_awaiting_scheduling()
        meeting = self.schedule_consultation(application)
        with self.assertRaises(MeetingDomainError):
            self.consultation_service.record_feedback(
                meeting=meeting,
                recorded_by=self.teacher,
                teacher_feedback="consultation_completed",
            )
        meeting.refresh_from_db()
        self.assertIsNone(meeting.teacher_feedback)
