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

    # TST-APP-010
    def test_e2e_cleanup_marca_inscricao_como_excluida(self) -> None:
        call_command("e2e_cleanup", "--protocol", self.application.protocol)

        self.assertFalse(
            ServiceApplication.objects.filter(pk=self.application.pk).exists()
        )
        persisted = ServiceApplication.all_objects.get(pk=self.application.pk)
        self.assertIsNotNone(persisted.soft_deleted_at)

    # TST-APP-011
    def test_e2e_cleanup_e_idempotente(self) -> None:
        call_command("e2e_cleanup", "--protocol", self.application.protocol)
        call_command("e2e_cleanup", "--protocol", self.application.protocol)

        persisted = ServiceApplication.all_objects.get(pk=self.application.pk)
        self.assertIsNotNone(persisted.soft_deleted_at)

    # TST-APP-012
    def test_e2e_cleanup_desativa_prefixo_preservando_seed(self) -> None:
        seed = User.objects.create_user(
            username="e2e_candidate",
            email="e2e_candidate@example.com",
            password="pass",
        )
        created = User.objects.create_user(
            username="cadastro_teste",
            email="e2e.cadastro.teste@example.com",
            password="pass",
        )
        call_command("e2e_cleanup", "--deactivate-prefix", "e2e.")
        seed.refresh_from_db()
        created.refresh_from_db()
        self.assertTrue(seed.is_active)
        self.assertFalse(created.is_active)

    # TST-APP-013
    def test_e2e_cleanup_purge_protocol_e_escopado(self) -> None:
        other = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality=ServiceApplication.Modality.CONSULTATION,
            researcher_name="Outra E2E",
            contact_email="outra@example.com",
        )
        call_command(
            "e2e_cleanup", "--purge-protocol", self.application.protocol
        )
        self.assertFalse(
            ServiceApplication.all_objects.filter(pk=self.application.pk).exists()
        )
        self.assertTrue(
            ServiceApplication.all_objects.filter(pk=other.pk).exists()
        )
