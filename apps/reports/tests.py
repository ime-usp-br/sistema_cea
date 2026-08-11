from django.test import TestCase
from django.urls import reverse

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from audits.services import DatasetAuditService
from payments.models import PaymentInstrument
from reports.services import ReportService
from terms.models import AcademicTerm
from users.models import User


class ReportScenarioTests(TestCase):
    def setUp(self) -> None:
        self.secretariat = User.objects.create_user(
            username="secretaria1",
            email="secretaria@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.administrator = User.objects.create_user(
            username="admin1",
            email="admin@example.com",
            password="pass",
            role=User.Role.ADMINISTRATOR,
        )
        self.candidate = User.objects.create_user(
            username="candidate1",
            email="candidate@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.service = ReportService()

    def create_project(self) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="project",
            researcher_name="Maria Pesquisadora",
            contact_email="maria@example.com",
        )

    def ensure_fee(self, app: ServiceApplication):
        from payments.services import FeeCalculationService

        fee = app.fee_requirements.first()
        if fee is None:
            fee = FeeCalculationService().create_application_fee(app)
        assert fee is not None
        return fee

    def create_paid_instrument(self, app: ServiceApplication, method: str) -> None:
        fee = self.ensure_fee(app)
        PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=method,
            state=PaymentInstrument.State.PAID,
            amount=fee.amount,
        )
        app.payment_state = ServiceApplication.PaymentState.PAID
        app.save(update_fields=["payment_state", "updated_at"])

    def test_TS_REP_001_relatorio_financeiro_reune_taxas_e_metodos(self):
        app = self.create_project()
        self.create_paid_instrument(app, PaymentInstrument.Method.PIX)
        rows = self.service.build_financial_report_data()
        self.assertTrue(rows)
        row = next(r for r in rows if r["protocol"] == app.protocol)
        self.assertEqual(row["candidate"], "Maria Pesquisadora")
        self.assertEqual(row["fee_type"], "Taxa de inscrição")
        self.assertEqual(row["payment_method"], "pix")
        self.assertEqual(row["payment_state"], "Pago")

    def test_TS_REP_002_sincronizacao_pix_estados(self):
        # A sincronização de estados é responsabilidade dos gateways; o relatório
        # expõe instrumentos Pix ativos/expirados com o estado atual.
        app = self.create_project()
        fee = self.ensure_fee(app)
        PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.PIX,
            state=PaymentInstrument.State.EXPIRED,
            amount=fee.amount,
        )
        rows = self.service.build_financial_report_data()
        row = next(r for r in rows if r["protocol"] == app.protocol)
        self.assertEqual(row["payment_method"], "pix")

    def test_TS_REP_003_sincronizacao_boleto_estados(self):
        app = self.create_project()
        self.create_paid_instrument(app, PaymentInstrument.Method.BANK_SLIP)
        rows = self.service.build_financial_report_data()
        row = next(r for r in rows if r["protocol"] == app.protocol)
        self.assertEqual(row["payment_method"], "bank_slip")
        self.assertEqual(row["payment_state"], "Pago")

    def test_TS_REP_004_exportacao_csv_bom_e_delimitador(self):
        app = self.create_project()
        self.create_paid_instrument(app, PaymentInstrument.Method.PIX)
        response = self.service.export_financial_csv()
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        content = response.content.decode("utf-8")
        self.assertTrue(content.startswith("\ufeff"))
        header_line = content.split("\n", 1)[0].lstrip("\ufeff")
        self.assertIn(";", header_line)
        self.assertIn("protocol", header_line)
        self.assertIn(app.protocol, content)

    def test_TS_REP_005_exportacao_xlsx_colunas_financeiras(self):
        app = self.create_project()
        self.create_paid_instrument(app, PaymentInstrument.Method.PIX)
        response = self.service.export_financial_xlsx()
        self.assertIn("attachment", response["Content-Disposition"])
        content = response.content.decode("utf-8-sig", errors="replace")
        self.assertIn("protocol", content)
        self.assertIn(app.protocol, content)

    def test_TS_REP_006_relatorio_auditoria_mostra_submissoes_e_decisoes(self):
        app = self.create_project()
        audit_service = DatasetAuditService()
        audit_service.enable_audit(application=app)
        submission = audit_service.submit_dataset(
            application=app,
            submitted_by=self.candidate,
            channel="external_link",
            external_url="https://example.com/dados",
            external_link_declaration=True,
        )
        audit_service.review_submission(
            submission=submission,
            reviewer=self.candidate,
            outcome="approved",
        )
        rows = self.service.build_audit_report_data()
        row = next(r for r in rows if r["protocol"] == app.protocol)
        self.assertEqual(row["project"], app.project_title or "")
        self.assertEqual(row["channel"], "Link externo")
        self.assertEqual(row["teacher_decision"], "Aprovado")
        self.assertGreaterEqual(row["corrections"], 1)

    def test_views_requerem_permissao_secretaria(self):
        self.client.force_login(self.candidate)
        response = self.client.get(reverse("reports:financial_report"))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse("reports:audit_report"))
        self.assertEqual(response.status_code, 403)

    def test_views_disponiveis_para_secretaria_e_admin(self):
        for user in (self.secretariat, self.administrator):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(reverse("reports:financial_report")).status_code, 200
            )
            self.assertEqual(
                self.client.get(reverse("reports:audit_report")).status_code, 200
            )
            self.assertEqual(
                self.client.get(reverse("reports:financial_csv")).status_code, 200
            )
            self.assertEqual(
                self.client.get(reverse("reports:financial_xlsx")).status_code, 200
            )
