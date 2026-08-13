import tempfile
from typing import cast

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.factories import build_valid_form_payload
from applications.models import ServiceApplication
from terms.factories import AcademicTermFactory
from terms.models import AcademicTerm
from users.factories import UserFactory

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-appform-media-"))
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

    # TS-APP-024
    def test_TS_APP_024_bloqueio_inscricao_projeto_fora_do_periodo(self) -> None:
        """Rejeita Projeto quando o termo está fora da janela de submissão (Gap 1)."""
        past_date = timezone.localdate() - timezone.timedelta(days=1)
        self.term.submission_start_date = past_date - timezone.timedelta(days=30)
        self.term.submission_end_date = past_date
        self.term.save()

        payload = build_valid_form_payload(
            modality="project", term_pk=self.term.pk
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("term", response.context["form"].errors)
        self.assertTrue(
            any(
                "fora do período" in str(err).lower()
                for err in response.context["form"].errors["term"]
            )
        )
        self.assertEqual(ServiceApplication.objects.count(), 0)

    # TS-APP-024 (variação) — Consulta em fluxo contínuo não é bloqueada
    def test_TS_APP_024_consulta_nao_e_bloqueada_fora_do_periodo(self) -> None:
        past_date = timezone.localdate() - timezone.timedelta(days=1)
        self.term.submission_start_date = past_date - timezone.timedelta(days=30)
        self.term.submission_end_date = past_date
        self.term.save()

        payload = build_valid_form_payload(
            modality="consultation", term_pk=self.term.pk
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceApplication.objects.count(), 1)

    # TS-FILE-GAP-001 — Segurança: rejeita extensões/MIME types executáveis.
    def test_TS_FILE_GAP_001_rejeita_arquivos_com_mime_types_nao_permitidos(self) -> None:
        payload = build_valid_form_payload(
            modality="consultation", term_pk=self.term.pk
        )
        bad_file = SimpleUploadedFile(
            "script.sh",
            b"#!/bin/bash\nrm -rf /",
            content_type="application/x-sh",
        )
        payload["attachments"] = [bad_file]
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachments", response.context["form"].errors)
        self.assertIn(
            "tipo de arquivo não permitido",
            str(response.context["form"].errors["attachments"]).lower(),
        )
        self.assertEqual(ServiceApplication.objects.count(), 0)

    def test_TS_FILE_GAP_001b_rejeita_extensao_perigosa_mesmo_sem_mime(self) -> None:
        payload = build_valid_form_payload(
            modality="consultation", term_pk=self.term.pk
        )
        bad_file = SimpleUploadedFile(
            "malware.exe",
            b"MZ\x90\x00\x03",
            content_type="application/octet-stream",
        )
        payload["attachments"] = [bad_file]
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachments", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 0)

    def test_TS_FILE_GAP_001c_aceita_pdf_valido(self) -> None:
        payload = build_valid_form_payload(
            modality="consultation", term_pk=self.term.pk
        )
        good_file = SimpleUploadedFile(
            "documento.pdf",
            b"%PDF-1.4 conteudo",
            content_type="application/pdf",
        )
        payload["attachments"] = [good_file]
        response = self._post(payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceApplication.objects.count(), 1)
