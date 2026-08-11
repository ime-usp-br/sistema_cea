import csv
import io
from decimal import Decimal
from typing import Any

from django.http import HttpResponse

from applications.models import ServiceApplication
from payments.models import PaymentInstrument

FINANCIAL_FIELDS = [
    "protocol",
    "modality",
    "candidate",
    "email",
    "fee_type",
    "payment_method",
    "base_amount",
    "adjustment_amount",
    "amount",
    "payment_state",
    "paid_at",
    "manual",
    "superseded",
    "modality_credit",
    "refund_status",
    "refund_amount",
]

AUDIT_FIELDS = [
    "protocol",
    "project",
    "candidate",
    "submitted_at",
    "channel",
    "audit_state",
    "submission_state",
    "teacher_decision",
    "admin_decision",
    "corrections",
]

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _fmt_money(value: Any) -> str:
    decimal_value = Decimal(str(value or "0"))
    return f"{decimal_value:.2f}"


def _fmt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, bool):
        return "sim" if value else "não"
    return str(value)


class ReportService:
    """Serviço de domínio responsável por relatórios financeiros e de auditoria."""

    # ---- Financeiro ----

    def build_financial_report_data(self) -> list[dict[str, Any]]:
        """Reúne inscrições, taxas, instrumentos e reembolsos (TS-REP-001)."""
        applications = (
            ServiceApplication.objects.select_related("term")
            .prefetch_related(
                "fee_requirements",
                "fee_requirements__payment_instruments",
                "refund_requests",
            )
            .order_by("protocol")
        )
        rows: list[dict[str, Any]] = []
        for app in applications:
            refund = app.refund_requests.order_by("-created_at").first()
            credit = app.modality_credit_amount or Decimal("0.00")
            fees = list(app.fee_requirements.all())
            if not fees:
                rows.append(self._financial_row(app, None, refund, credit))
                continue
            for fee in fees:
                instrument = fee.payment_instruments.first()
                rows.append(self._financial_row(app, fee, refund, credit, instrument))
        return rows

    def _financial_row(
        self,
        app: ServiceApplication,
        fee: Any,
        refund: Any,
        credit: Decimal,
        instrument: Any = None,
    ) -> dict[str, Any]:
        return {
            "protocol": app.protocol,
            "modality": app.get_modality_display(),
            "candidate": app.researcher_name,
            "email": app.legacy_contact_email or app.contact_email or "",
            "fee_type": fee.get_fee_type_display() if fee else "",
            "payment_method": instrument.method if instrument else "",
            "base_amount": fee.base_amount if fee else Decimal("0.00"),
            "adjustment_amount": fee.adjustment_amount if fee else Decimal("0.00"),
            "amount": fee.amount if fee else Decimal("0.00"),
            "payment_state": app.get_payment_state_display() if app.payment_state else "",
            "paid_at": (instrument.paid_at.isoformat() if instrument and instrument.paid_at else None),
            "manual": bool(instrument and instrument.state == PaymentInstrument.State.MANUAL_CONFIRMED),
            "superseded": bool(instrument and instrument.state == PaymentInstrument.State.SUPERSEDED),
            "modality_credit": credit,
            "refund_status": refund.get_status_display() if refund else "",
            "refund_amount": refund.amount if refund else Decimal("0.00"),
        }

    def export_financial_csv(self) -> HttpResponse:
        """Exporta o relatório financeiro em CSV com separador `;` e BOM UTF-8 (TS-REP-004)."""
        rows = self.build_financial_report_data()
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="relatorio_financeiro.csv"'
        response.write("\ufeff")
        writer = csv.DictWriter(
            response, fieldnames=FINANCIAL_FIELDS, delimiter=";", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: _fmt_value(row.get(field)) for field in FINANCIAL_FIELDS}
            )
        return response

    def export_financial_xlsx(self) -> HttpResponse:
        """Exporta o relatório financeiro em XLSX (fallback TSV se openpyxl ausente - TS-REP-005)."""
        rows = self.build_financial_report_data()
        try:
            import openpyxl  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError:
            return self._export_financial_tsv_fallback(rows)
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Financeiro"
        worksheet.append(FINANCIAL_FIELDS)
        for row in rows:
            worksheet.append([row.get(field) for field in FINANCIAL_FIELDS])
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = 'attachment; filename="relatorio_financeiro.xlsx"'
        return response

    def _export_financial_tsv_fallback(self, rows: list[dict[str, Any]]) -> HttpResponse:
        buffer = io.StringIO()
        buffer.write("\ufeff")
        writer = csv.DictWriter(
            buffer, fieldnames=FINANCIAL_FIELDS, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: _fmt_value(row.get(field)) for field in FINANCIAL_FIELDS}
            )
        response = HttpResponse(
            buffer.getvalue(), content_type="text/tab-separated-values; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="relatorio_financeiro.tsv"'
        return response

    # ---- Auditoria ----

    def build_audit_report_data(self) -> list[dict[str, Any]]:
        """Reúne submissões, revisões e decisões de auditoria (TS-REP-006)."""
        applications = (
            ServiceApplication.objects.filter(dataset_audit_required=True)
            .prefetch_related(
                "audit_submissions",
                "audit_submissions__reviews",
                "audit_submissions__resolutions",
            )
            .order_by("protocol")
        )
        rows: list[dict[str, Any]] = []
        for app in applications:
            submissions = list(app.audit_submissions.all())
            if not submissions:
                continue
            for submission in submissions:
                review = submission.reviews.first()
                resolution = submission.resolutions.first()
                rows.append(
                    {
                        "protocol": app.protocol,
                        "project": app.project_title or "",
                        "candidate": app.researcher_name,
                        "submitted_at": (
                            submission.submitted_at.isoformat() if submission.submitted_at else None
                        ),
                        "channel": submission.get_submission_channel_display(),
                        "audit_state": (
                            app.get_dataset_audit_state_display()
                            if app.dataset_audit_state
                            else ""
                        ),
                        "submission_state": submission.get_state_display(),
                        "teacher_decision": review.get_outcome_display() if review else "",
                        "admin_decision": (
                            resolution.get_resolution_display() if resolution else ""
                        ),
                        "corrections": submission.reviews.count(),
                    }
                )
        return rows

    def export_audit_csv(self) -> HttpResponse:
        rows = self.build_audit_report_data()
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="relatorio_auditoria.csv"'
        response.write("\ufeff")
        writer = csv.DictWriter(
            response, fieldnames=AUDIT_FIELDS, delimiter=";", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _fmt_value(row.get(field)) for field in AUDIT_FIELDS})
        return response
