"""Teste do botão/rota de habilitar auditoria manual (D10 / TS-AUD-016)."""

import tempfile
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import ApplicationEvent, ServiceApplication
from payments.models import FeeRequirement
from terms.models import AcademicTerm
from users.models import User


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-enable-audit-"))
class EnableAuditViewTests(TestCase):
    def setUp(self) -> None:
        self.secretariat = User.objects.create_user(
            username="sec_audit",
            email="sec_audit@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
            is_email_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="cand_audit",
            email="cand_audit@example.com",
            password="pass",
            is_email_verified=True,
        )
        self.term = AcademicTerm.objects.create(year=2030, period="first")
        self.application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            modality=ServiceApplication.Modality.PROJECT,
            protocol="123123123",
            researcher_name="Auditoria Manual",
            contact_email=self.candidate.email,
            dataset_audit_required=False,
        )
        FeeRequirement.objects.create(
            application=self.application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=Decimal("80.00"),
            amount=Decimal("80.00"),
        )

    def test_TS_AUD_016_habilitar_auditoria_pela_ficha(self) -> None:
        self.client.force_login(self.secretariat)
        response = self.client.post(
            reverse("audits:enable_audit", args=[self.application.protocol])
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertTrue(self.application.dataset_audit_required)
        self.assertEqual(
            self.application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=self.application, event_code="audit.enabled"
            ).exists()
        )

    def test_TS_AUD_016_candidato_nao_pode_habilitar(self) -> None:
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("audits:enable_audit", args=[self.application.protocol])
        )
        self.assertEqual(response.status_code, 403)
