import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from audits.models import (
    DatasetAuditResolution,
    DatasetAuditSubmission,
)
from audits.services import DatasetAuditError, DatasetAuditService, validate_external_url
from files.models import FileAsset
from terms.models import AcademicTerm
from users.models import User


def _file(name: str = "dados.csv", content: bytes = b"coluna_a,coluna_b\n1,2\n") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="text/csv")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-audit-media-"))
class AuditScenarioTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate1",
            email="candidate1@example.com",
            password="pass",
        )
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
        self.future_term = AcademicTerm.objects.create(year=2026, period="second")
        self.service = DatasetAuditService()

    def create_project(self, owner: User | None = None) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=owner or self.candidate,
            modality="project",
            researcher_name="Maria Pesquisadora",
            contact_email="maria@example.com",
        )

    def create_imported_project(self) -> ServiceApplication:
        return ServiceApplication.all_objects.create(
            term=self.term,
            owner=None,
            protocol="999000111",
            modality="project",
            lifecycle_status=ServiceApplication.LifecycleStatus.SUBMITTED,
            origin=ServiceApplication.Origin.IMPORTED,
            dataset_audit_required=False,
            researcher_name="Importado",
            contact_email="importado@example.com",
        )

    def submit_file(self, application: ServiceApplication, **kwargs) -> DatasetAuditSubmission:
        return self.service.submit_dataset(
            application=application,
            submitted_by=self.candidate,
            channel="file",
            uploaded_file=kwargs.get("file", _file()),
            note=kwargs.get("note"),
        )

    def submit_link(
        self,
        application: ServiceApplication,
        url: str = "https://example.com/dados",
        **kwargs,
    ) -> DatasetAuditSubmission:
        return self.service.submit_dataset(
            application=application,
            submitted_by=self.candidate,
            channel="external_link",
            external_url=url,
            external_link_declaration=True,
            note=kwargs.get("note"),
        )

    # TS-AUD-001
    def test_TS_AUD_001_projeto_com_dono_exige_auditoria(self) -> None:
        application = self.create_project()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.assertTrue(application.dataset_audit_required)
        self.assertEqual(
            application.dataset_audit_state,
            ServiceApplication.DatasetAuditState.AWAITING_SUBMISSION,
        )
        self.assertEqual(DatasetAuditSubmission.objects.count(), 0)

    # TS-AUD-002
    def test_TS_AUD_002_projeto_importado_sem_dono_nao_entra_em_auditoria(self) -> None:
        application = self.create_imported_project()
        self.assertEqual(application.origin, ServiceApplication.Origin.IMPORTED)
        self.assertIsNone(application.owner_id)
        self.assertFalse(application.dataset_audit_required)
        self.assertIsNone(application.dataset_audit_state)

    # TS-AUD-003
    def test_TS_AUD_003_envio_de_arquivo_valido(self) -> None:
        application = self.create_project()
        submission = self.submit_file(application)
        self.assertEqual(submission.submission_channel, "file")
        self.assertIsNotNone(submission.file_asset_id)
        self.assertIsNone(submission.external_url)
        self.assertFalse(submission.external_link_declaration)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW,
        )
        assert submission.file_asset_id is not None
        asset = FileAsset.objects.get(pk=submission.file_asset_id)
        self.assertEqual(asset.purpose, FileAsset.Purpose.DATASET_SUBMISSION)

    # TS-AUD-004
    def test_TS_AUD_004_envio_de_arquivo_acima_de_10mb(self) -> None:
        application = self.create_project()
        big = SimpleUploadedFile(
            "grande.csv",
            b"x" * (10 * 1024 * 1024 + 1),
            content_type="text/csv",
        )
        with self.assertRaises(DatasetAuditError):
            self.service.submit_dataset(
                application=application,
                submitted_by=self.candidate,
                channel="file",
                uploaded_file=big,
            )
        self.assertEqual(DatasetAuditSubmission.objects.count(), 0)
        self.assertEqual(FileAsset.objects.count(), 0)

    # TS-AUD-005
    def test_TS_AUD_005_envio_de_link_externo(self) -> None:
        application = self.create_project()
        submission = self.submit_link(application, url="https://drive.example.com/dados")
        self.assertEqual(submission.submission_channel, "external_link")
        self.assertEqual(submission.external_url, "https://drive.example.com/dados")
        self.assertTrue(submission.external_link_declaration)
        self.assertIsNone(submission.file_asset_id)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW,
        )

    # TS-AUD-006
    def test_TS_AUD_006_link_externo_invalido(self) -> None:
        application = self.create_project()
        with self.assertRaises(DatasetAuditError):
            self.submit_link(application, url="ftp://example.com/dados")
        with self.assertRaises(DatasetAuditError):
            self.submit_link(application, url="not-a-url")
        with self.assertRaises(DatasetAuditError):
            self.submit_link(application, url="javascript:alert(1)")
        self.assertEqual(DatasetAuditSubmission.objects.count(), 0)

    # TS-AUD-007
    def test_TS_AUD_007_link_sem_declaracao_de_acesso(self) -> None:
        from audits.forms import DatasetSubmissionForm

        application = self.create_project()
        with self.assertRaises(DatasetAuditError):
            self.service.submit_dataset(
                application=application,
                submitted_by=self.candidate,
                channel="external_link",
                external_url="https://example.com/dados",
                external_link_declaration=False,
            )
        form = DatasetSubmissionForm(
            data={
                "channel": "external_link",
                "external_url": "https://example.com/dados",
                "external_link_declaration": False,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("external_link_declaration", form.errors)
        self.assertEqual(DatasetAuditSubmission.objects.count(), 0)

    # TS-AUD-008
    def test_TS_AUD_008_submissao_nao_aceita_arquivo_e_link_simultaneos(self) -> None:
        application = self.create_project()
        with self.assertRaises(DatasetAuditError):
            self.service.submit_dataset(
                application=application,
                submitted_by=self.candidate,
                channel="file",
                uploaded_file=_file(),
                external_url="https://example.com/dados",
            )
        with self.assertRaises(DatasetAuditError):
            self.service.submit_dataset(
                application=application,
                submitted_by=self.candidate,
                channel="external_link",
                external_url="https://example.com/dados",
                external_link_declaration=True,
                uploaded_file=_file(),
            )
        self.assertEqual(DatasetAuditSubmission.objects.count(), 0)

        with self.assertRaises(IntegrityError), transaction.atomic():
            DatasetAuditSubmission.objects.create(
                application=application,
                submitted_by=self.candidate,
                submission_channel="file",
                file_asset=None,
                external_url=None,
            )

    # TS-AUD-009
    def test_TS_AUD_009_docente_solicita_correcao(self) -> None:
        application = self.create_project()
        submission = self.submit_file(application)
        review = self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="needs_correction",
            note="Reenvie com a coluna de datas",
        )
        self.assertEqual(review.outcome, "needs_correction")
        submission.refresh_from_db()
        self.assertEqual(submission.state, DatasetAuditSubmission.State.NEEDS_CORRECTION)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_CORRECTION,
        )
        self.assertEqual(
            application.dataset_audit_state,
            ServiceApplication.DatasetAuditState.NEEDS_CORRECTION,
        )

    # TS-AUD-010
    def test_TS_AUD_010_candidato_corrige_e_reenvia(self) -> None:
        application = self.create_project()
        first = self.submit_file(application)
        self.service.review_submission(
            submission=first,
            reviewer=self.teacher,
            outcome="needs_correction",
            note="Corrija",
        )
        second = self.service.submit_dataset(
            application=application,
            submitted_by=self.candidate,
            channel="file",
            uploaded_file=_file(name="corrigido.csv", content=b"ok\n"),
        )
        self.assertEqual(DatasetAuditSubmission.objects.count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.state, DatasetAuditSubmission.State.NEEDS_CORRECTION)
        self.assertEqual(second.state, DatasetAuditSubmission.State.SUBMITTED)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW,
        )

    # TS-AUD-011
    def test_TS_AUD_011_docente_aprova_auditoria(self) -> None:
        application = self.create_project()
        submission = self.submit_file(application)
        review = self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="approved",
        )
        self.assertEqual(review.outcome, "approved")
        submission.refresh_from_db()
        self.assertEqual(submission.state, DatasetAuditSubmission.State.APPROVED)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )
        self.assertEqual(
            application.dataset_audit_state,
            ServiceApplication.DatasetAuditState.APPROVED,
        )
        fee = application.fee_requirements.get(
            fee_type="application_fee", base_amount="80.00"
        )
        self.assertEqual(fee.amount, Decimal("80.00"))

    # TS-AUD-012
    def test_TS_AUD_012_docente_rejeita_auditoria(self) -> None:
        application = self.create_project()
        submission = self.submit_file(application)
        self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="rejected",
            note="Dados insuficientes",
        )
        submission.refresh_from_db()
        self.assertEqual(submission.state, DatasetAuditSubmission.State.REJECTED)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.DATASET_REJECTED_PENDING_RESOLUTION,
        )
        self.assertEqual(DatasetAuditResolution.objects.count(), 0)

    # TS-AUD-013
    def test_TS_AUD_013_secretaria_converte_em_consulta(self) -> None:
        application = self.create_project()
        submission = self.submit_file(application)
        self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="rejected",
        )
        resolution = self.service.resolve_rejection(
            submission=submission,
            decided_by=self.secretariat,
            resolution="convert_to_consultation",
            note="Converter",
        )
        self.assertEqual(resolution.resolution, "convert_to_consultation")
        application.refresh_from_db()
        self.assertEqual(application.modality, ServiceApplication.Modality.CONSULTATION)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_PAYMENT,
        )
        self.assertFalse(application.dataset_audit_required)
        fee = application.fee_requirements.get(
            fee_type="application_fee", base_amount="140.00"
        )
        self.assertEqual(fee.amount, Decimal("140.00"))

    # TS-AUD-014
    def test_TS_AUD_014_secretaria_rejeita_inscricao(self) -> None:
        application = self.create_project()
        submission = self.submit_file(application)
        self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="rejected",
        )
        resolution = self.service.resolve_rejection(
            submission=submission,
            decided_by=self.secretariat,
            resolution="reject_application",
        )
        self.assertEqual(resolution.resolution, "reject_application")
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.NOT_APPROVED,
        )
        self.assertEqual(DatasetAuditResolution.objects.count(), 1)

    # TS-AUD-015
    def test_TS_AUD_015_secretaria_transfere_de_periodo(self) -> None:
        application = self.create_project()
        submission = self.submit_file(application)
        self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="rejected",
        )
        self.service.resolve_rejection(
            submission=submission,
            decided_by=self.secretariat,
            resolution="transfer_term",
            target_term=self.future_term,
            note="Transferir para próximo período",
        )
        application.refresh_from_db()
        self.assertEqual(application.term_id, self.future_term.pk)
        self.assertEqual(DatasetAuditSubmission.objects.filter(application=application).count(), 1)
        resolution = DatasetAuditResolution.objects.get()
        self.assertEqual(resolution.resolution, "transfer_term")
        self.assertEqual(resolution.target_term_id, self.future_term.pk)

    # TS-AUD-016
    def test_TS_AUD_016_auditoria_habilitada_apos_resgate(self) -> None:
        application = self.create_imported_project()
        application.owner = self.candidate
        application.save(update_fields=["owner", "updated_at"])
        self.service.enable_audit(application=application)
        application.refresh_from_db()
        self.assertTrue(application.dataset_audit_required)
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.assertEqual(
            application.dataset_audit_state,
            ServiceApplication.DatasetAuditState.AWAITING_SUBMISSION,
        )

    # TS-AUD-017
    def test_TS_AUD_017_link_inacessivel_docente_solicita_correcao(self) -> None:
        application = self.create_project()
        submission = self.submit_link(application, url="https://offline.example.com/dados")
        review = self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="needs_correction",
            note="Link inacessível, reenvie o link válido",
        )
        self.assertEqual(review.outcome, "needs_correction")
        submission.refresh_from_db()
        self.assertEqual(submission.state, DatasetAuditSubmission.State.NEEDS_CORRECTION)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_CORRECTION,
        )

    def test_TS_AUD_017b_link_inacessivel_docente_rejeita(self) -> None:
        application = self.create_project()
        submission = self.submit_link(application, url="https://offline.example.com/dados")
        self.service.review_submission(
            submission=submission,
            reviewer=self.teacher,
            outcome="rejected",
            note="Link inacessível",
        )
        submission.refresh_from_db()
        self.assertEqual(submission.state, DatasetAuditSubmission.State.REJECTED)
        application.refresh_from_db()
        self.assertEqual(
            application.lifecycle_status,
            ServiceApplication.LifecycleStatus.DATASET_REJECTED_PENDING_RESOLUTION,
        )

    def test_validate_external_url_helper(self) -> None:
        self.assertEqual(
            validate_external_url("https://example.com/p"),
            "https://example.com/p",
        )
        self.assertEqual(
            validate_external_url("http://example.com/p"),
            "http://example.com/p",
        )
        with self.assertRaises(DatasetAuditError):
            validate_external_url("")

    # TS-AUD-GAP-001 — SSRF: bloqueia loopback e endereços de rede local/interna.
    def test_TS_AUD_GAP_001_link_externo_nao_pode_apontar_para_localhost_ssrf(self) -> None:
        application = self.create_project()
        bad_urls = [
            "http://localhost/admin",
            "http://127.0.0.1:8000",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.5/",
            "http://172.16.0.10/",
            "http://192.168.1.1/",
            "http://[::1]/",
            "http://metadata.google.internal/",
        ]
        for bad_url in bad_urls:
            with self.subTest(url=bad_url), self.assertRaises(
                DatasetAuditError, msg=f"A URL {bad_url} deveria ser bloqueada."
            ):
                self.submit_link(application, url=bad_url)
        self.assertEqual(DatasetAuditSubmission.objects.count(), 0)

    def test_TS_AUD_GAP_001b_url_publica_continua_aceita(self) -> None:
        """Garante que a proteção SSRF não rejeita URLs públicas legítimas."""
        application = self.create_project()
        submission = self.submit_link(
            application, url="https://drive.example.com/dados"
        )
        self.assertEqual(submission.submission_channel, "external_link")
        self.assertEqual(
            submission.external_url, "https://drive.example.com/dados"
        )
