import os
import tempfile
from datetime import timedelta
from typing import Any

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from applications.models import ApplicationEvent, ServiceApplication
from audits.models import DatasetAuditSubmission
from audits.services import DatasetAuditService
from files.models import FileAsset
from imports.importers import LegacyImporter
from imports.models import LegacyOwnershipClaim
from imports.services import LegacyClaimError, LegacyClaimService
from payments.models import PaymentInstrument
from terms.models import AcademicTerm
from users.models import User

EAGER_EMAIL = override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")

LEGACY_RECORD: dict[str, Any] = {
    "protocol": "200000001",
    "modality": "project",
    "researcher_name": "Carla Importada",
    "contact_email": "carla@example.com",
    "tax_id": "33333333333",
    "legacy_contact_email": "carla@example.com",
    "legacy_contact_tax_id": "33333333333",
    "project_title": "Projeto legado B",
    "lifecycle_status": ServiceApplication.LifecycleStatus.SUBMITTED,
    "term": {"year": 2025, "period": "first"},
}


class LegacyImportScenarioTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate1",
            email="carla@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.secretariat = User.objects.create_user(
            username="secretaria1",
            email="secretaria@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.term = AcademicTerm.objects.create(year=2025, period="first")
        self.importer = LegacyImporter()

    def import_record(self, record: dict) -> ServiceApplication:
        report = self.importer.import_records([record])
        self.assertEqual(report.errors, [])
        return report.created[0]

    def test_TS_IMP_001_inscricao_importada_sem_dono_preserva_contatos(self):
        app = self.import_record(LEGACY_RECORD)
        self.assertEqual(app.origin, ServiceApplication.Origin.IMPORTED)
        self.assertIsNone(app.owner_id)
        self.assertEqual(app.legacy_contact_email, "carla@example.com")
        self.assertEqual(app.legacy_contact_tax_id, "33333333333")

    def test_TS_IMP_002_importada_nao_aparece_no_painel_do_candidato(self):
        app = self.import_record(LEGACY_RECORD)
        apps = ServiceApplication.objects.filter(owner=self.candidate)
        self.assertNotIn(app, list(apps))
        self.assertEqual(apps.count(), 0)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-import-media-"))
    def test_TS_IMP_003_anexos_importados_criam_file_asset(self):
        import hashlib

        with tempfile.TemporaryDirectory() as root:
            content = b"%PDF-1.4 exemplo"
            legacy_path = os.path.join(root, "documento.pdf")
            with open(legacy_path, "wb") as handle:
                handle.write(content)
            record = dict(LEGACY_RECORD)
            record["attachments"] = [
                {
                    "legacy_path": "documento.pdf",
                    "content_type": "application/pdf",
                }
            ]
            importer = LegacyImporter(attachments_root=root)
            report = importer.import_records([record])
            self.assertEqual(report.errors, [])
            app = report.created[0]
            file_asset = FileAsset.objects.filter(application=app).first()
            self.assertIsNotNone(file_asset)
            assert file_asset is not None
            self.assertEqual(
                file_asset.sha256_checksum, hashlib.sha256(content).hexdigest()
            )
            self.assertTrue(app.attachments.filter(file_asset=file_asset).exists())

    def test_TS_IMP_004_pagamentos_preservados(self):
        record = dict(LEGACY_RECORD)
        record["payments"] = [
            {
                "method": "bank_slip",
                "state": "paid",
                "amount": "80.00",
                "reason": "Taxa importada",
            },
            {
                "method": "manual",
                "state": "manual_confirmed",
                "amount": "60.00",
                "reason": "Pagamento manual importado",
            },
        ]
        app = self.import_record(record)
        states = set(
            PaymentInstrument.objects.filter(
                fee_requirement__application=app
            ).values_list("state", flat=True)
        )
        self.assertIn(PaymentInstrument.State.PAID, states)
        self.assertIn(PaymentInstrument.State.MANUAL_CONFIRMED, states)
        self.assertEqual(app.payment_state, ServiceApplication.PaymentState.PAID)

    def test_TS_IMP_005_projeto_importado_sem_auditoria_automatica(self):
        app = self.import_record(LEGACY_RECORD)
        self.assertFalse(app.dataset_audit_required)
        self.assertIsNone(app.dataset_audit_state)
        self.assertEqual(DatasetAuditSubmission.objects.filter(application=app).count(), 0)

    def test_TS_IMP_006_transferencia_preserva_ausencia_de_dono(self):
        app = self.import_record(LEGACY_RECORD)
        app.term = self.term
        app.save(update_fields=["term", "updated_at"])
        app.refresh_from_db()
        self.assertIsNone(app.owner_id)
        self.assertFalse(app.dataset_audit_required)

    def test_TS_IMP_007_protocolos_duplicados_detectados(self):
        self.import_record(LEGACY_RECORD)
        report = self.importer.import_records([LEGACY_RECORD])
        self.assertEqual(report.created, [])
        self.assertTrue(any("duplicado" in error for error in report.errors))

    def test_TS_IMP_008_arquivos_ausentes_relatados(self):
        with tempfile.TemporaryDirectory() as root:
            importer = LegacyImporter(attachments_root=root)
            record = dict(LEGACY_RECORD)
            record["attachments"] = [{"legacy_path": "nao_existe.pdf"}]
            report = importer.import_records([record])
            self.assertTrue(report.created)
            self.assertIn("nao_existe.pdf", report.missing_files)

    def test_management_command_importa_dados_de_exemplo(self):
        call_command("import_legacy_data")
        self.assertEqual(
            ServiceApplication.objects.filter(
                origin=ServiceApplication.Origin.IMPORTED
            ).count(),
            2,
        )


class LegacyClaimScenarioTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate1",
            email="carla@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.secretariat = User.objects.create_user(
            username="secretaria1",
            email="secretaria@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.term = AcademicTerm.objects.create(year=2025, period="first")
        self.service = LegacyClaimService()
        report = LegacyImporter().import_records([LEGACY_RECORD])
        self.application = report.created[0]

    @EAGER_EMAIL
    def test_TS_CLAIM_001_solicitacao_cria_claim(self):
        claim, _token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        self.assertIsNotNone(claim.pk)
        self.assertIn(
            claim.status,
            {LegacyOwnershipClaim.Status.PENDING, LegacyOwnershipClaim.Status.CODE_SENT},
        )

    @EAGER_EMAIL
    def test_TS_CLAIM_002_codigo_enviado_como_hash_com_expiracao(self):
        claim, token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(token, mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["carla@example.com"])
        self.assertIsNotNone(claim.verification_token_hash)
        self.assertNotEqual(claim.verification_token_hash, token)
        self.assertIsNotNone(claim.code_expires_at)

    @EAGER_EMAIL
    def test_TS_CLAIM_003_codigo_correto_vincula_inscricao(self):
        claim, token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        verified = self.service.confirm_claim(
            user=self.candidate, claim_id=claim.pk, code=token
        )
        self.application.refresh_from_db()
        self.assertEqual(verified.status, LegacyOwnershipClaim.Status.VERIFIED)
        self.assertEqual(self.application.owner, self.candidate)
        self.assertIsNotNone(verified.verified_at)
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=self.application, event_code="claim.verified"
            ).exists()
        )

    @EAGER_EMAIL
    def test_TS_CLAIM_004_codigo_incorreto_nao_vincula_e_limita(self):
        claim, _token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        for _ in range(5):
            with self.assertRaises(LegacyClaimError):
                self.service.confirm_claim(
                    user=self.candidate, claim_id=claim.pk, code="000000"
                )
        claim.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(claim.status, LegacyOwnershipClaim.Status.REJECTED)
        self.assertIsNone(self.application.owner_id)

    @EAGER_EMAIL
    def test_TS_CLAIM_005_codigo_expirado_rejeitado(self):
        claim, token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        claim.code_expires_at = timezone.now() - timedelta(minutes=1)
        claim.save(update_fields=["code_expires_at", "updated_at"])
        with self.assertRaises(LegacyClaimError):
            self.service.confirm_claim(
                user=self.candidate, claim_id=claim.pk, code=token
            )
        self.application.refresh_from_db()
        self.assertIsNone(self.application.owner_id)

    @EAGER_EMAIL
    def test_TS_CLAIM_006_sem_vinculacao_automatica_silenciosa(self):
        # E-mail da conta é idêntico ao e-mail legado; mesmo assim, sem confirmação
        # a inscrição não é vinculada.
        claim, _token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        self.application.refresh_from_db()
        self.assertIsNone(self.application.owner_id)
        self.assertIn(
            claim.status,
            {LegacyOwnershipClaim.Status.PENDING, LegacyOwnershipClaim.Status.CODE_SENT},
        )

    @EAGER_EMAIL
    def test_TS_CLAIM_007_aprovacao_manual_pela_secretaria(self):
        claim, _token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        approved = self.service.manually_approve_claim(
            claim=claim,
            secretariat_user=self.secretariat,
            note="Documento validado pela secretaria.",
        )
        self.application.refresh_from_db()
        self.assertEqual(approved.status, LegacyOwnershipClaim.Status.MANUALLY_APPROVED)
        self.assertEqual(approved.reviewed_by, self.secretariat)
        self.assertEqual(approved.review_note, "Documento validado pela secretaria.")
        self.assertEqual(self.application.owner, self.candidate)

    @EAGER_EMAIL
    def test_TS_CLAIM_008_inscricao_resgatada_pode_entrar_em_auditoria(self):
        claim, token = self.service.request_claim(
            user=self.candidate,
            protocol=self.application.protocol,
            contact_email_or_tax_id="carla@example.com",
        )
        self.service.confirm_claim(
            user=self.candidate, claim_id=claim.pk, code=token
        )
        self.application.refresh_from_db()
        DatasetAuditService().enable_audit(application=self.application)
        self.application.refresh_from_db()
        self.assertTrue(self.application.dataset_audit_required)
        self.assertEqual(
            self.application.dataset_audit_state,
            ServiceApplication.DatasetAuditState.AWAITING_SUBMISSION,
        )
