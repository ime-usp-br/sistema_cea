from datetime import date, time
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

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

    # TS-MEET-013
    def test_TS_MEET_013_reagendamento_trocando_modo_limpa_campos_corretamente(self) -> None:
        """Trocar Online -> Presencial limpa o link antigo sem disparar erro (Gap 2)."""
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(
            application,
            meeting_mode="online",
            virtual_link="https://meet.google.com/abc",
            place=None,
        )

        rescheduled = self.screening_service.reschedule_screening(
            screening=screening,
            rescheduled_by=self.secretariat,
            scheduled_date=FUTURE_DATE,
            scheduled_time=FUTURE_TIME,
            meeting_mode="in_person",
            virtual_link=None,
            place="Sala 1 - IME",
        )

        rescheduled.refresh_from_db()
        self.assertEqual(rescheduled.meeting_mode, "in_person")
        self.assertEqual(rescheduled.place, "Sala 1 - IME")
        self.assertIsNone(rescheduled.virtual_link)

    # TS-MEET-013 (consulta) — mesma transição no fluxo de reuniões
    def test_TS_MEET_013_reagendamento_consulta_troca_para_online_limpa_local(self) -> None:
        application = self.consultation_awaiting_scheduling()
        meeting = self.schedule_consultation(
            application,
            meeting_mode="in_person",
            virtual_link=None,
            place="Sala 1 - IME",
        )

        rescheduled = self.consultation_service.reschedule_consultation(
            meeting=meeting,
            rescheduled_by=self.secretariat,
            scheduled_date=FUTURE_DATE,
            scheduled_time=FUTURE_TIME,
            meeting_mode="online",
            virtual_link="https://meet.google.com/xyz",
            place=None,
        )

        rescheduled.refresh_from_db()
        self.assertEqual(rescheduled.meeting_mode, "online")
        self.assertEqual(rescheduled.virtual_link, "https://meet.google.com/xyz")
        self.assertIsNone(rescheduled.place)

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

    # TS-MEET-GAP-002 — triagem CONCLUÍDA não pode ser cancelada (taxa órfã)
    def test_TS_MEET_GAP_002_nao_cancela_triagem_concluida(self) -> None:
        """Paridade Laravel: decisão final (COMPLETED) protege contra cancelamento."""
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        screening = self.screening_service.record_decision(
            screening=screening,
            decided_by=self.teacher,
            decision="approved_as_project",
        )
        self.assertEqual(screening.state, ProjectScreening.State.COMPLETED)

        with self.assertRaisesMessage(
            MeetingDomainError, "Triagens concluídas não podem ser canceladas."
        ):
            self.screening_service.cancel_screening(
                screening=screening, canceled_by=self.secretariat
            )

        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT,
        )
        # A taxa de projeto (R$ 250) deve permanecer ativa na inscrição
        self.assertTrue(
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.PROJECT_FEE
            ).exists()
        )

    # TS-MEET-GAP-003 — reunião CONCLUÍDA não pode ser cancelada
    def test_TS_MEET_GAP_003_nao_cancela_reuniao_concluida(self) -> None:
        application = self.consultation_awaiting_scheduling()
        meeting = self.schedule_consultation(application)
        meeting = self.consultation_service.record_decision(
            meeting=meeting,
            decided_by=self.teacher,
            decision="approved_as_consultation",
        )
        self.assertEqual(meeting.state, ConsultationMeeting.State.COMPLETED)

        with self.assertRaisesMessage(
            MeetingDomainError, "Reuniões concluídas não podem ser canceladas."
        ):
            self.consultation_service.cancel_consultation(
                meeting=meeting, canceled_by=self.secretariat
            )

        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_CONSULTATION,
        )


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

    # TS-MEET-GAP-001 — Docente não pode decidir/feedbackar triagem CANCELADA.
    def test_TS_MEET_GAP_001_decisao_bloqueada_em_triagem_cancelada(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        self.screening_service.cancel_screening(
            screening=screening, canceled_by=self.secretariat
        )
        screening.refresh_from_db()
        self.assertEqual(screening.state, ProjectScreening.State.CANCELED)

        with self.assertRaises(MeetingDomainError):
            self.screening_service.record_decision(
                screening=screening,
                decided_by=self.teacher,
                decision="approved_as_project",
            )
        screening.refresh_from_db()
        self.assertIsNone(screening.decision)
        self.assertEqual(screening.state, ProjectScreening.State.CANCELED)

    def test_TS_MEET_GAP_001b_feedback_bloqueado_em_triagem_cancelada(self) -> None:
        application = self.project_awaiting_scheduling()
        screening = self.screening_service.schedule_screening(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=PAST_DATE,
            scheduled_time=PAST_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/sala",
        )
        self.screening_service.cancel_screening(
            screening=screening, canceled_by=self.secretariat
        )
        screening.refresh_from_db()
        self.assertEqual(screening.state, ProjectScreening.State.CANCELED)

        with self.assertRaises(MeetingDomainError):
            self.screening_service.record_feedback(
                screening=screening,
                recorded_by=self.teacher,
                teacher_feedback="screening_completed",
            )
        screening.refresh_from_db()
        self.assertIsNone(screening.teacher_feedback)
        self.assertEqual(screening.state, ProjectScreening.State.CANCELED)

    # TS-MEET-GAP-001 (consulta) — mesmo bloqueio para reuniões de Consulta.
    def test_TS_MEET_GAP_001c_decisao_bloqueada_em_reuniao_cancelada(self) -> None:
        application = self.consultation_awaiting_scheduling()
        meeting = self.schedule_consultation(application)
        self.consultation_service.cancel_consultation(
            meeting=meeting, canceled_by=self.secretariat
        )
        meeting.refresh_from_db()
        self.assertEqual(meeting.state, ConsultationMeeting.State.CANCELED)

        with self.assertRaises(MeetingDomainError):
            self.consultation_service.record_decision(
                meeting=meeting,
                decided_by=self.teacher,
                decision="approved_as_consultation",
            )
        meeting.refresh_from_db()
        self.assertIsNone(meeting.decision)
        self.assertEqual(meeting.state, ConsultationMeeting.State.CANCELED)

    def test_TS_MEET_GAP_001d_feedback_bloqueado_em_reuniao_cancelada(self) -> None:
        application = self.consultation_awaiting_scheduling()
        meeting = self.consultation_service.schedule_consultation(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=PAST_DATE,
            scheduled_time=PAST_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/sala",
        )
        self.consultation_service.cancel_consultation(
            meeting=meeting, canceled_by=self.secretariat
        )
        meeting.refresh_from_db()
        self.assertEqual(meeting.state, ConsultationMeeting.State.CANCELED)

        with self.assertRaises(MeetingDomainError):
            self.consultation_service.record_feedback(
                meeting=meeting,
                recorded_by=self.teacher,
                teacher_feedback="consultation_completed",
            )
        meeting.refresh_from_db()
        self.assertIsNone(meeting.teacher_feedback)
        self.assertEqual(meeting.state, ConsultationMeeting.State.CANCELED)

    # TS-MEET-014 — Consulta aprovada como Projeto gera Taxa de Projeto (Gap 2)
    def test_TS_MEET_014_consulta_aprovada_como_projeto_gera_taxa_de_projeto(self) -> None:
        """
        No Laravel, na reunião de Consulta, o Docente pode decidir promovê-la a
        Projeto. Isso cria automaticamente o bankSlip de 250 (R$ 250,00).
        """
        application = self.consultation_awaiting_scheduling()
        meeting = self.schedule_consultation(application)

        self.consultation_service.record_decision(
            meeting=meeting,
            decided_by=self.teacher,
            decision="approved_as_project",
        )

        application.refresh_from_db()
        self.assertEqual(application.modality, ServiceApplication.Modality.PROJECT)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT,
        )

        project_fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.PROJECT_FEE
        )
        self.assertEqual(project_fee.amount, Decimal("250.00"))
        self.assertTrue(
            application.events.filter(
                event_code="meeting.consultation_decided"
            ).exists()
        )

    # TS-MOD-GAP-003 — triagem agendada é cancelada ao converter Projeto -> Consulta
    def test_TS_MOD_GAP_003_mudanca_de_modalidade_cancela_triagem_agendada(self) -> None:
        """Paridade com o Laravel: mudar Projeto para Consulta não deixa a triagem
        agendada órfã no banco — ela deve ser cancelada via ProjectScreeningService."""
        from payments.services import ModalityChangeService

        application = self.project_awaiting_scheduling()
        screening = self.schedule_project(application)
        self.assertEqual(
            screening.state, ProjectScreening.State.SCHEDULED
        )
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_RESULT,
        )

        ModalityChangeService().convert_to_consultation(
            application=application, decided_by=self.secretariat
        )

        screening.refresh_from_db()
        application.refresh_from_db()
        self.assertEqual(
            screening.state,
            ProjectScreening.State.CANCELED,
            "A triagem agendada deveria ter sido cancelada na conversão para Consulta.",
        )
        self.assertEqual(application.modality, ServiceApplication.Modality.CONSULTATION)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )
        self.assertTrue(
            application.events.filter(event_code="meeting.screening_canceled").exists()
        )


class MeetingViewTests(TestCase):
    """Testes das telas de agendamento, decisão e feedback (apps/meetings/views.py)."""

    def setUp(self) -> None:
        self.teacher = User.objects.create_user(
            username="teacher_view",
            email="teacher_view@example.com",
            password="pass",
            role=User.Role.TEACHER,
        )
        self.secretariat = User.objects.create_user(
            username="secretariat_view",
            email="secretariat_view@example.com",
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
    ) -> ServiceApplication:
        return ServiceApplication.objects.create(
            term=self.term,
            owner=owner or self.teacher,
            protocol=protocol,
            modality=modality,
            lifecycle_status=lifecycle_status,
            modality_credit_amount=Decimal("0.00"),
            researcher_name="Maria Pesquisadora",
            contact_email="maria@example.com",
        )

    def project_awaiting(self) -> ServiceApplication:
        return self._application(
            modality="project",
            lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING,
            protocol="333000333",
        )

    def consultation_awaiting(self) -> ServiceApplication:
        return self._application(
            modality="consultation",
            lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
            protocol="444000444",
        )

    def schedule_project(
        self, application: ServiceApplication, scheduled_date: date = FUTURE_DATE
    ) -> ProjectScreening:
        return self.screening_service.schedule_screening(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=scheduled_date,
            scheduled_time=FUTURE_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/sala",
        )

    # Fila de agendamentos (/agendamentos/)
    def test_view_fila_requer_autenticacao(self) -> None:
        response = self.client.get(reverse("meetings:queue"))
        self.assertEqual(response.status_code, 302)

    def test_view_fila_exibe_projetos_e_consultas_aguardando(self) -> None:
        self.client.force_login(self.secretariat)
        proj = self.project_awaiting()
        cons = self.consultation_awaiting()
        response = self.client.get(reverse("meetings:queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, proj.protocol)
        self.assertContains(response, cons.protocol)

    def test_view_fila_bloqueia_candidato(self) -> None:
        candidate = User.objects.create_user(
            username="candidate_view",
            email="candidate_view@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.client.force_login(candidate)
        response = self.client.get(reverse("meetings:queue"))
        self.assertEqual(response.status_code, 403)

    # Agendamento de triagem (/agendamentos/triagem/<protocol>/)
    def test_view_screening_schedule_get(self) -> None:
        self.client.force_login(self.secretariat)
        proj = self.project_awaiting()
        response = self.client.get(
            reverse("meetings:screening_schedule", args=[proj.protocol])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["application"], proj)

    def test_view_screening_schedule_post_online(self) -> None:
        self.client.force_login(self.secretariat)
        proj = self.project_awaiting()
        response = self.client.post(
            reverse("meetings:screening_schedule", args=[proj.protocol]),
            {
                "scheduled_date": "2099-01-01",
                "scheduled_time": "10:00",
                "meeting_mode": "online",
                "virtual_link": "https://meet.example.com/sala",
            },
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        proj.refresh_from_db()
        self.assertEqual(
            proj.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_RESULT,
        )
        self.assertEqual(ProjectScreening.objects.filter(application=proj).count(), 1)

    def test_view_screening_schedule_post_presencial_exige_local(self) -> None:
        self.client.force_login(self.secretariat)
        proj = self.project_awaiting()
        response = self.client.post(
            reverse("meetings:screening_schedule", args=[proj.protocol]),
            {
                "scheduled_date": "2099-01-01",
                "scheduled_time": "10:00",
                "meeting_mode": "in_person",
                "place": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProjectScreening.objects.filter(application=proj).count(), 0)

    def test_view_screening_schedule_cancel(self) -> None:
        self.client.force_login(self.secretariat)
        proj = self.project_awaiting()
        screening = self.schedule_project(proj)
        response = self.client.post(
            reverse("meetings:screening_schedule", args=[proj.protocol]),
            {"action": "cancel"},
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        screening.refresh_from_db()
        self.assertEqual(screening.state, ProjectScreening.State.CANCELED)

    # Agendamento de reunião de consulta (/agendamentos/reuniao/<protocol>/)
    def test_view_consultation_schedule_post_online(self) -> None:
        self.client.force_login(self.secretariat)
        cons = self.consultation_awaiting()
        response = self.client.post(
            reverse("meetings:consultation_schedule", args=[cons.protocol]),
            {
                "scheduled_date": "2099-01-01",
                "scheduled_time": "10:00",
                "meeting_mode": "online",
                "virtual_link": "https://meet.example.com/sala",
            },
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        cons.refresh_from_db()
        self.assertEqual(
            cons.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_RESULT,
        )
        self.assertEqual(ConsultationMeeting.objects.filter(application=cons).count(), 1)

    def test_view_consultation_schedule_cancel(self) -> None:
        self.client.force_login(self.secretariat)
        cons = self.consultation_awaiting()
        meeting = self.consultation_service.schedule_consultation(
            application=cons,
            scheduled_by=self.secretariat,
            scheduled_date=FUTURE_DATE,
            scheduled_time=FUTURE_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/sala",
        )
        response = self.client.post(
            reverse("meetings:consultation_schedule", args=[cons.protocol]),
            {"action": "cancel"},
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        meeting.refresh_from_db()
        self.assertEqual(meeting.state, ConsultationMeeting.State.CANCELED)

    # Decisão de triagem (/agendamentos/triagem/<id>/decisao/)
    def test_view_screening_decision_aprovado_como_projeto(self) -> None:
        self.client.force_login(self.teacher)
        proj = self.project_awaiting()
        screening = self.schedule_project(proj)
        response = self.client.post(
            reverse("meetings:screening_decision", args=[screening.pk]),
            {"decision": "approved_as_project", "decision_note": "Aprovado"},
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        proj.refresh_from_db()
        self.assertEqual(
            proj.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT,
        )
        fee = proj.fee_requirements.get(fee_type=FeeRequirement.FeeType.PROJECT_FEE)
        self.assertEqual(fee.amount, Decimal("250.00"))

    def test_view_screening_decision_nao_aprovado(self) -> None:
        self.client.force_login(self.teacher)
        proj = self.project_awaiting()
        screening = self.schedule_project(proj)
        response = self.client.post(
            reverse("meetings:screening_decision", args=[screening.pk]),
            {"decision": "not_approved", "decision_note": "Recusado"},
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        proj.refresh_from_db()
        self.assertEqual(
            proj.lifecycle_status, ServiceApplication.LifecycleStatus.NOT_APPROVED
        )

    def test_view_screening_feedback_bloqueado_antes_do_evento(self) -> None:
        self.client.force_login(self.teacher)
        proj = self.project_awaiting()
        screening = self.schedule_project(proj)
        response = self.client.post(
            reverse("meetings:screening_decision", args=[screening.pk]),
            {"submit_feedback": "1", "teacher_feedback": "screening_completed"},
        )
        self.assertEqual(response.status_code, 400)
        screening.refresh_from_db()
        self.assertIsNone(screening.teacher_feedback)

    def test_view_screening_feedback_registrado_apos_evento(self) -> None:
        self.client.force_login(self.teacher)
        proj = self.project_awaiting()
        screening = self.schedule_project(proj, scheduled_date=PAST_DATE)
        response = self.client.post(
            reverse("meetings:screening_decision", args=[screening.pk]),
            {"submit_feedback": "1", "teacher_feedback": "screening_completed"},
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        screening.refresh_from_db()
        self.assertEqual(
            screening.teacher_feedback,
            ProjectScreening.TeacherFeedback.SCREENING_COMPLETED,
        )

    # Decisão de reunião de consulta (/agendamentos/reuniao/<id>/decisao/)
    def test_view_consultation_decision_aprovado(self) -> None:
        self.client.force_login(self.teacher)
        cons = self.consultation_awaiting()
        meeting = self.consultation_service.schedule_consultation(
            application=cons,
            scheduled_by=self.secretariat,
            scheduled_date=FUTURE_DATE,
            scheduled_time=FUTURE_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/sala",
        )
        response = self.client.post(
            reverse("meetings:consultation_decision", args=[meeting.pk]),
            {"decision": "approved_as_consultation", "decision_note": "Aprovado"},
        )
        self.assertRedirects(response, reverse("meetings:queue"))
        cons.refresh_from_db()
        self.assertEqual(
            cons.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_CONSULTATION,
        )
