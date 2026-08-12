import hashlib
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.factories import build_valid_form_payload
from applications.forms import ApplicationForm
from applications.models import CatalogOption, ServiceApplication
from applications.services import ApplicationSubmissionService, ProtocolGenerator
from applications.validators import validate_br_tax_id
from files.models import FileAsset
from terms.models import AcademicTerm
from users.models import User


class FixedProtocolGenerator(ProtocolGenerator):
    def __init__(self, protocols: list[str]) -> None:
        self.protocols = list(protocols)

    def generate(self) -> str:
        return self.protocols.pop(0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-media-"))
class ApplicationScenarioTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="candidate1",
            email="candidate1@example.com",
            password="pass",
        )
        self.other_user = User.objects.create_user(
            username="candidate2",
            email="candidate2@example.com",
            password="pass",
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")

    def login(self) -> None:
        self.client.force_login(self.user)

    def post_application(self, *, modality: str = "project", data=None, files=None):
        # Base 100% válida (dados sintéticos Faker) conforme as regras de
        # validação vigentes; `data` sobrescreve campos pontualmente.
        payload = build_valid_form_payload(modality=modality, term_pk=self.term.pk)
        payload.update(data or {})
        if files:
            payload.update(files)
        return self.client.post(reverse("applications:create"), payload)

    def create_application(self, *, modality: str = "consultation", **kwargs) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.user,
            modality=modality,
            researcher_name="Maria Pesquisadora",
            contact_email="maria@example.com",
            **kwargs,
        )

    def test_TS_APP_001_painel_mostra_apenas_inscricoes_proprias(self) -> None:
        own = self.create_application(modality="project")
        other = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.other_user,
            modality="consultation",
            researcher_name="João Pesquisador",
            contact_email="joao@example.com",
        )
        imported = ServiceApplication.all_objects.create(
            term=self.term,
            owner=None,
            protocol="123456789",
            modality="project",
            lifecycle_status=ServiceApplication.LifecycleStatus.SUBMITTED,
            origin=ServiceApplication.Origin.IMPORTED,
            researcher_name="Importado",
            contact_email="importado@example.com",
        )
        self.login()
        response = self.client.get(reverse("applications:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own.protocol)
        self.assertNotContains(response, other.protocol)
        self.assertNotContains(response, imported.protocol)
        self.assertQuerySetEqual(ServiceApplication.objects.filter(owner=self.user), [own])

    def test_TS_APP_002_criacao_projeto_por_candidato(self) -> None:
        self.login()
        response = self.post_application(modality="project")
        application = ServiceApplication.objects.get()
        self.assertRedirects(
            response,
            reverse("applications:detail", args=[application.protocol]),
        )
        self.assertEqual(application.origin, ServiceApplication.Origin.CREATED_PORTAL)
        self.assertEqual(application.owner, self.user)
        self.assertEqual(application.modality, ServiceApplication.Modality.PROJECT)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.assertTrue(application.dataset_audit_required)

    def test_TS_APP_003_criacao_consulta_por_candidato(self) -> None:
        self.login()
        response = self.post_application(modality="consultation")
        application = ServiceApplication.objects.get()
        self.assertRedirects(
            response,
            reverse("applications:detail", args=[application.protocol]),
        )
        self.assertEqual(application.modality, ServiceApplication.Modality.CONSULTATION)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )
        self.assertFalse(application.dataset_audit_required)

    def test_TS_APP_004_protocolo_unico_com_9_digitos(self) -> None:
        first = self.create_application(modality="project")
        self.assertEqual(len(first.protocol), 9)
        self.assertRegex(first.protocol, r"^\d{9}$")

        colliding = FixedProtocolGenerator([first.protocol, "000000001"])
        service = ApplicationSubmissionService(protocol_generator=colliding)
        second = service.create_application(
            term=self.term,
            owner=self.user,
            modality="project",
            researcher_name="Maria Pesquisadora",
            contact_email="maria@example.com",
        )
        self.assertEqual(second.protocol, "000000001")
        self.assertNotEqual(second.protocol, first.protocol)
        self.assertEqual(ServiceApplication.objects.all_with_deleted().count(), 2)

    def test_TS_APP_005_campos_obrigatorios(self) -> None:
        form = ApplicationForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("term", form.errors)
        self.assertIn("modality", form.errors)
        self.assertIn("researcher_name", form.errors)
        self.assertIn("contact_email", form.errors)

        self.login()
        response = self.post_application(data={"researcher_name": "", "contact_email": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("researcher_name", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 0)

    def test_TS_APP_006_validacao_de_cpf_cnpj(self) -> None:
        self.assertEqual(validate_br_tax_id("529.982.247-25"), "52998224725")
        self.assertEqual(validate_br_tax_id("11.222.333/0001-81"), "11222333000181")
        with self.assertRaises(ValidationError):
            validate_br_tax_id("111.111.111-11")
        with self.assertRaises(ValidationError):
            validate_br_tax_id("11.222.333/0001-00")

        self.login()
        response = self.post_application(
            modality="consultation",
            data={"tax_id": "529.982.247-25"},
        )
        application = ServiceApplication.objects.get()
        self.assertEqual(application.tax_id, "52998224725")

        response = self.post_application(
            modality="consultation",
            data={"tax_id": "111.111.111-11"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("tax_id", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 1)

    def test_TS_APP_007_opcoes_de_catalogo_com_outro(self) -> None:
        self.assertEqual(CatalogOption.objects.filter(category="institutional_tie").count(), 4)
        self.assertEqual(CatalogOption.objects.filter(category="project_purpose").count(), 6)
        self.assertEqual(CatalogOption.objects.filter(category="knowledge_area").count(), 5)
        self.assertEqual(CatalogOption.objects.filter(category="funding_agency").count(), 4)

        student = CatalogOption.objects.get(category="institutional_tie", code="student")
        other = CatalogOption.objects.get(category="institutional_tie", code="other")

        self.login()

        # Regra de exclusividade por seção: Estudante + Outro são rejeitados.
        response = self.post_application(
            modality="project",
            data={"catalog_options": [str(student.pk), str(other.pk)]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("catalog_options", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 0)

        # Selecionar apenas "Outro" sem texto complementar exige preenchimento.
        response = self.post_application(
            modality="project",
            data={"catalog_options": [str(other.pk)], "catalog_other_text": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("catalog_other_text", response.context["form"].errors)
        self.assertEqual(ServiceApplication.objects.count(), 0)

        # Selecionar apenas "Outro" com texto é aceito e salva other_text.
        response = self.post_application(
            modality="project",
            data={
                "catalog_options": [str(other.pk)],
                "catalog_other_text": "Outro vínculo institucional",
            },
        )
        self.assertEqual(response.status_code, 302)
        application = ServiceApplication.objects.get()
        selections = application.catalog_selections.all()
        self.assertEqual(selections.count(), 1)
        self.assertEqual(selections.get(option=other).other_text, "Outro vínculo institucional")

    def test_TS_APP_008_anexos_de_inscricao(self) -> None:
        self.login()
        files = [
            SimpleUploadedFile("anexo1.txt", b"conteudo 1", content_type="text/plain"),
            SimpleUploadedFile("anexo2.txt", b"conteudo 2", content_type="text/plain"),
        ]
        response = self.post_application(modality="project", files={"attachments": files})
        self.assertEqual(response.status_code, 302)
        application = ServiceApplication.objects.get()
        self.assertEqual(FileAsset.objects.count(), 2)
        self.assertEqual(application.attachments.count(), 2)
        asset = FileAsset.objects.get(original_filename="anexo1.txt")
        self.assertEqual(asset.purpose, FileAsset.Purpose.APPLICATION_ATTACHMENT)
        self.assertEqual(asset.application_id, application.pk)
        self.assertEqual(asset.uploaded_by_id, self.user.pk)
        self.assertEqual(asset.size_bytes, len(b"conteudo 1"))
        self.assertEqual(asset.sha256_checksum, hashlib.sha256(b"conteudo 1").hexdigest())

    def test_TS_APP_009_anexos_acima_do_limite(self) -> None:
        self.login()
        big = SimpleUploadedFile(
            "grande.bin",
            b"x" * (8 * 1024 * 1024 + 1),
            content_type="application/octet-stream",
        )
        response = self.post_application(modality="project", files={"attachments": [big]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachments", response.context["form"].errors)
        self.assertEqual(FileAsset.objects.count(), 0)
        self.assertEqual(ServiceApplication.objects.count(), 0)

    def test_TS_APP_010_exclusao_logica(self) -> None:
        application = self.create_application(modality="consultation")
        application.soft_delete()
        self.assertIsNotNone(application.soft_deleted_at)
        self.assertNotIn(application, ServiceApplication.objects.all())
        self.assertIn(application, ServiceApplication.objects.all_with_deleted())
        application.restore()
        self.assertIsNone(application.soft_deleted_at)
        self.assertIn(application, ServiceApplication.objects.all())
