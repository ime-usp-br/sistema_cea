"""Testes das telas de Triagens e Reuniões de Consulta (Fase 3).

Verifica o default do filtro por semestre e a ausência da coluna "Taxa
Projeto" na tela de Reuniões, conforme legado.
"""

from __future__ import annotations

from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from meetings.models import ConsultationMeeting, ProjectScreening
from meetings.services import ConsultationMeetingService, ProjectScreeningService
from terms.models import AcademicTerm
from users.models import User

FUTURE_DATE = date(2099, 1, 1)
FUTURE_TIME = time(10, 0)


class MeetingsScreeningConsultationTests(TestCase):
    def setUp(self) -> None:
        self.term_first = AcademicTerm.objects.create(year=2026, period="first")
        self.term_second = AcademicTerm.objects.create(year=2026, period="second")
        self.secretariat = User.objects.create_user(
            username="sec",
            email="sec@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.teacher = User.objects.create_user(
            username="doc",
            email="doc@example.com",
            password="pass",
            role=User.Role.TEACHER,
        )

    def _screening(self, term: AcademicTerm) -> ProjectScreening:
        owner = User.objects.create_user(
            username=f"cand{User.objects.count()}",
            email=f"cand{User.objects.count()}@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        application = ApplicationSubmissionService().create_application(
            term=term,
            owner=owner,
            modality=ServiceApplication.Modality.PROJECT,
            researcher_name="Pesquisador",
            contact_email="p@example.com",
        )
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
        )
        application.save(update_fields=["lifecycle_status"])
        return ProjectScreeningService().schedule_screening(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=FUTURE_DATE,
            scheduled_time=FUTURE_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/x",
        )

    def _meeting(self, term: AcademicTerm) -> ConsultationMeeting:
        owner = User.objects.create_user(
            username=f"cand{User.objects.count()}",
            email=f"cand{User.objects.count()}@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        application = ApplicationSubmissionService().create_application(
            term=term,
            owner=owner,
            modality=ServiceApplication.Modality.CONSULTATION,
            researcher_name="Pesquisador",
            contact_email="p@example.com",
        )
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
        )
        application.save(update_fields=["lifecycle_status"])
        return ConsultationMeetingService().schedule_consultation(
            application=application,
            scheduled_by=self.secretariat,
            scheduled_date=FUTURE_DATE,
            scheduled_time=FUTURE_TIME,
            meeting_mode="online",
            virtual_link="https://meet.example.com/x",
        )

    # TS-MTG-TRIAGENS-DEFAULT
    def test_TS_MTG_TRIAGENS_filtra_por_semestre_atual_por_default(self) -> None:
        first = self._screening(self.term_first)
        second = self._screening(self.term_second)
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("meetings:screening_list"))
        self.assertContains(response, second.application.protocol)
        self.assertNotContains(response, first.application.protocol)

    # TS-MTG-REUNIOES-SEM-TAXA-PROJETO
    def test_TS_MTG_REUNIOES_nao_tem_coluna_taxa_projeto(self) -> None:
        self._meeting(self.term_second)
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("meetings:consultation_list"))
        self.assertContains(response, "Reuniões de Consulta")
        self.assertNotContains(response, "Taxa Projeto")

    # TS-MTG-TRIAGENS-COM-TAXA-PROJETO (Secretaria)
    def test_TS_MTG_TRIAGENS_exibe_taxa_projeto_para_secretaria(self) -> None:
        self._screening(self.term_second)
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("meetings:screening_list"))
        self.assertContains(response, "Taxa Projeto")

    # TS-MTG-TRIAGENS-SEM-TAXA-PROJETO (Docente - T3.3)
    def test_TS_MTG_TRIAGENS_esconde_taxa_projeto_para_docente(self) -> None:
        self._screening(self.term_second)
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("meetings:screening_list"))
        self.assertNotContains(response, "Taxa Projeto")

    # TS-MTG-ALIAS-QUEUE
    def test_TS_MEET_015_alias_queue_continua_disponivel(self) -> None:
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("meetings:queue"))
        self.assertEqual(response.status_code, 200)
