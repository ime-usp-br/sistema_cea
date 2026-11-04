"""Testes do comando de cleanup dos dados E2E (T3.1)."""

from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from terms.models import AcademicTerm
from users.models import User


class E2ECleanupCommandTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.candidate = User.objects.create_user(
            username="cleanup_candidate",
            email="cleanup@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.application = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality=ServiceApplication.Modality.CONSULTATION,
            researcher_name="Cleanup E2E",
            contact_email="cleanup@example.com",
        )

    def test_e2e_cleanup_marca_inscricao_como_excluida(self) -> None:
        call_command("e2e_cleanup", "--protocol", self.application.protocol)

        self.assertFalse(
            ServiceApplication.objects.filter(pk=self.application.pk).exists()
        )
        persisted = ServiceApplication.all_objects.get(pk=self.application.pk)
        self.assertIsNotNone(persisted.soft_deleted_at)

    def test_e2e_cleanup_e_idempotente(self) -> None:
        call_command("e2e_cleanup", "--protocol", self.application.protocol)
        call_command("e2e_cleanup", "--protocol", self.application.protocol)

        persisted = ServiceApplication.all_objects.get(pk=self.application.pk)
        self.assertIsNotNone(persisted.soft_deleted_at)
