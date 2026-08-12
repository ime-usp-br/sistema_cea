from typing import cast

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from applications.factories import build_valid_form_payload
from applications.models import ServiceApplication
from terms.factories import AcademicTermFactory
from terms.models import AcademicTerm
from users.factories import UserFactory

User = get_user_model()


class ApplicationFormFakerTest(TestCase):
    """Simula o preenchimento literal do formulário de inscrição.

    Usa Client.post com payload 100% válido gerado por Faker. O objetivo é
    provar que uma ficha completa e realista passa pela validação do
    ApplicationForm e gera a inscrição no estado correto.
    """

    def setUp(self) -> None:
        self.term: AcademicTerm = AcademicTermFactory()  # type: ignore[assignment]
        self.user: User = cast(User, UserFactory())
        self.client.force_login(self.user)

    def _post(self, payload) -> HttpResponse:
        return self.client.post(reverse("applications:create"), payload)

    def test_payload_completo_cria_projeto(self) -> None:
        payload = build_valid_form_payload(modality="project", term_pk=self.term.pk)
        response = self._post(payload)
        self.assertEqual(response.status_code, 302)
        application = ServiceApplication.objects.get()
        self.assertEqual(application.owner, self.user)
        self.assertEqual(application.modality, ServiceApplication.Modality.PROJECT)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.assertTrue(application.dataset_audit_required)
        self.assertTrue(application.catalog_selections.exists())

    def test_payload_completo_cria_consulta_com_taxa(self) -> None:
        payload = build_valid_form_payload(modality="consultation", term_pk=self.term.pk)
        response = self._post(payload)
        self.assertEqual(response.status_code, 302)
        application = ServiceApplication.objects.get()
        self.assertEqual(application.modality, ServiceApplication.Modality.CONSULTATION)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )
        self.assertFalse(application.dataset_audit_required)
        self.assertTrue(application.fee_requirements.exists())

    def test_payload_cpf_invalido_rejeitado(self) -> None:
        payload = build_valid_form_payload(
            modality="consultation",
            term_pk=self.term.pk,
            tax_id="111.111.111-11",
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("tax_id", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 0)

    def test_payload_campos_obrigatorios_ausentes_rejeitado(self) -> None:
        payload = build_valid_form_payload(
            modality="project",
            term_pk=self.term.pk,
            researcher_name="",
            contact_email="",
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("researcher_name", response.context["form"].errors)
        self.assertIn("contact_email", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 0)

    def test_payload_catalogo_duplicado_por_secao_rejeitado(self) -> None:
        from applications.models import CatalogOption

        student = CatalogOption.objects.get(category="institutional_tie", code="student")
        other = CatalogOption.objects.get(category="institutional_tie", code="other")
        payload = build_valid_form_payload(
            modality="project",
            term_pk=self.term.pk,
            catalog_options=[str(student.pk), str(other.pk)],
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("catalog_options", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 0)
