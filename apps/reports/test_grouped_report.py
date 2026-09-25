"""Testes do relatório financeiro agrupado por inscrição (Fase 6)."""

from __future__ import annotations

from django.test import TestCase

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from payments.models import FeeRequirement
from payments.services import FeeCalculationService
from reports.services import ReportService
from terms.models import AcademicTerm
from users.models import User


class GroupedFinancialReportTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.candidate = User.objects.create_user(
            username="candidate",
            email="c@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.service = ReportService()

    def test_TS_REP_AGRUPADO_uma_linha_por_inscricao_com_tres_taxas(self) -> None:
        application = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality=ServiceApplication.Modality.PROJECT,
            researcher_name="Maria",
            contact_email="c@example.com",
        )
        FeeCalculationService().create_project_fee(application)
        FeeCalculationService().create_supplement_fee(application)
        rows = self.service.build_financial_report_data()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["protocol"], application.protocol)
        self.assertEqual(
            set(row["fees"].keys()),
            {
                FeeRequirement.FeeType.APPLICATION_FEE.value,
                FeeRequirement.FeeType.PROJECT_FEE.value,
                FeeRequirement.FeeType.SUPPLEMENT_FEE.value,
            },
        )

    def test_TS_REP_EXPORT_FILENAME_usa_semestre(self) -> None:
        response = self.service.export_financial_csv(term=self.term)
        self.assertIn(
            "relatorio_financeiro_2026_first.csv",
            response["Content-Disposition"],
        )
