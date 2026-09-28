"""Testes da transferência pendente e da migração automática (D5 / TS-TRM)."""

import tempfile
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import ApplicationEvent, ServiceApplication
from applications.services import TermTransferService
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.factories import SecretariatFactory, UserFactory


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-transfer-media-"))
class TermTransferPendingTests(TestCase):
    def setUp(self) -> None:
        self.candidate = UserFactory()
        self.secretariat = SecretariatFactory()
        self.term = AcademicTerm.objects.create(year=2100, period="first")

    def _application(self, modality: str = "project") -> ServiceApplication:
        application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            modality=modality,
            protocol=f"{ServiceApplication.objects.count() + 1:09d}",
            researcher_name="Pesquisador Transferência",
            contact_email=self.candidate.email,
        )
        FeeRequirement.objects.create(
            application=application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=Decimal("80.00"),
            amount=Decimal("80.00"),
        )
        return application

    def test_TS_TRM_002_sem_proximo_periodo_fica_pendente(self) -> None:
        application = self._application()
        self.client.force_login(self.secretariat)
        response = self.client.post(
            reverse("applications:transfer_semester", args=[application.protocol])
        )
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertTrue(application.transfer_pending)
        self.assertIsNotNone(application.transfer_reason)
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=application, event_code="term.transfer_pending"
            ).exists()
        )

    def test_TS_TRM_003_criar_periodo_migra_e_reseta_status(self) -> None:
        project = self._application("project")
        consultation = self._application("consultation")
        service = TermTransferService()
        service.transfer_to_next_semester(project, decided_by=self.secretariat)
        service.transfer_to_next_semester(consultation, decided_by=self.secretariat)
        project.refresh_from_db()
        consultation.refresh_from_db()
        self.assertTrue(project.transfer_pending)
        self.assertTrue(consultation.transfer_pending)

        new_term = AcademicTerm.objects.create(year=2100, period="second")

        project.refresh_from_db()
        consultation.refresh_from_db()
        self.assertEqual(project.term_id, new_term.pk)
        self.assertEqual(consultation.term_id, new_term.pk)
        self.assertFalse(project.transfer_pending)
        self.assertFalse(consultation.transfer_pending)
        self.assertEqual(
            project.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING,
        )
        self.assertEqual(
            consultation.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING,
        )
        self.assertEqual(
            ApplicationEvent.objects.filter(
                application__in=[project, consultation],
                event_code="term.transfer_auto",
            ).count(),
            2,
        )

    def test_TS_TRM_editar_periodo_nao_remigra(self) -> None:
        application = self._application()
        TermTransferService().transfer_to_next_semester(
            application, decided_by=self.secretariat
        )
        application.refresh_from_db()
        self.assertTrue(application.transfer_pending)

        # Editar o período existente (created=False) não dispara migração.
        self.term.year = 2100
        self.term.save()

        application.refresh_from_db()
        self.assertTrue(application.transfer_pending)
        self.assertEqual(application.term_id, self.term.pk)

    def test_TS_TRM_004_005_preserva_auditoria_e_pagamentos(self) -> None:
        application = self._application()
        fee = application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )
        instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.PIX,
            state=PaymentInstrument.State.PAID,
            amount=fee.amount,
        )
        TermTransferService().transfer_to_next_semester(
            application, decided_by=self.secretariat
        )
        new_term = AcademicTerm.objects.create(year=2100, period="second")
        application.refresh_from_db()
        self.assertEqual(application.term_id, new_term.pk)
        self.assertEqual(application.fee_requirements.count(), 1)
        self.assertTrue(
            PaymentInstrument.objects.filter(
                pk=instrument.pk, fee_requirement__application=application
            ).exists()
        )
        self.assertEqual(application.events.filter(event_code="term.transfer_auto").count(), 1)
