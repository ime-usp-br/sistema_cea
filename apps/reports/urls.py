from django.urls import path

from .views import (
    AuditReportView,
    FinancialExportCsvView,
    FinancialExportXlsxView,
    FinancialReportView,
)

app_name = "reports"

urlpatterns = [
    path(
        "gestao/relatorios/financeiro/",
        FinancialReportView.as_view(),
        name="financial_report",
    ),
    path(
        "gestao/relatorios/financeiro/csv/",
        FinancialExportCsvView.as_view(),
        name="financial_csv",
    ),
    path(
        "gestao/relatorios/financeiro/xlsx/",
        FinancialExportXlsxView.as_view(),
        name="financial_xlsx",
    ),
    path(
        "gestao/relatorios/auditoria/",
        AuditReportView.as_view(),
        name="audit_report",
    ),
]
