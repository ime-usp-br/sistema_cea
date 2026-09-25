import csv
import io
from decimal import Decimal
from typing import Any

from django.http import HttpResponse

from applications.models import ServiceApplication
from payments.models import FeeRequirement, PaymentInstrument
from payments.services import fee_status_label

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

# Cabeçalhos do export (paridade com ``FinancialReportController`` legado).
FINANCIAL_EXPORT_HEADERS = [
    "Protocolo",
    "Modalidade",
    "Pesquisador",
    "CPF",
    "E-mail",
    "Nome (Boleto)",
    "CPF/CNPJ (Boleto)",
    "Banco",
    "Agência",
    "Conta",
    "Tipo",
    "Recibo Reembolso",
    "Dados Reembolso",
    "Taxa de Inscrição",
    "Taxa de Projeto",
    "Complemento",
]

FEE_ORDER = [
    FeeRequirement.FeeType.APPLICATION_FEE.value,
    FeeRequirement.FeeType.PROJECT_FEE.value,
    FeeRequirement.FeeType.SUPPLEMENT_FEE.value,
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
    """Serviço de domínio responsável por relatórios financeiros e de auditoria.

    O relatório financeiro é agrupado por inscrição (paridade com o sistema
    legado): cada linha tem uma célula por taxa (inscrição / projeto /
    complemento). Os exportadores (CSV/XLSX) seguem o mesmo formato.
    """

    # ---- Financeiro (agrupado por inscrição) ----

    def build_financial_report_data(self, term: Any = None) -> list[dict[str, Any]]:
        applications = (
            ServiceApplication.objects.select_related("term")
            .prefetch_related(
                "fee_requirements",
                "fee_requirements__payment_instruments",
                "refund_requests",
            )
            .order_by("protocol")
        )
        if term is not None:
            applications = applications.filter(term=term)
        return [self._financial_row(app) for app in applications]

    def _financial_row(self, app: ServiceApplication) -> dict[str, Any]:
        refund = app.refund_requests.order_by("-created_at").first()
        fees = list(app.fee_requirements.all())
        fees_by_type = {fee.fee_type: fee for fee in fees}
        credit = app.modality_credit_amount or Decimal("0.00")

        fee_cells: dict[str, dict[str, Any]] = {}
        for fee_type in FEE_ORDER:
            fee = fees_by_type.get(fee_type)
            if fee is None:
                fee_cells[fee_type] = {
                    "label": "Não Emitido",
                    "amount": None,
                    "status": "Não Emitido",
                    "method": "",
                    "manual": False,
                    "superseded": False,
                    "bank_status": "",
                    "due_date": None,
                    "paid_date": None,
                }
                continue
            instruments = list(fee.payment_instruments.all())
            instrument = instruments[0] if instruments else None
            slip = getattr(instrument, "bank_slip_instrument", None) if instrument else None
            fee_cells[fee_type] = {
                "label": fee.get_fee_type_display(),
                "amount": fee.amount,
                "status": fee_status_label(fee),
                "method": instrument.method if instrument else "",
                "manual": bool(
                    instrument
                    and instrument.state == PaymentInstrument.State.MANUAL_CONFIRMED
                ),
                "superseded": bool(
                    instrument
                    and instrument.state == PaymentInstrument.State.SUPERSEDED
                ),
                "bank_status": slip.get_bank_status_display() if slip else "",
                "due_date": slip.due_date if slip else None,
                "paid_date": slip.payment_date if slip else (
                    instrument.paid_at if instrument else None
                ),
            }

        return {
            "application": app,
            "protocol": app.protocol,
            "modality": app.get_modality_display(),
            "candidate": app.researcher_name,
            "tax_id": app.tax_id or "",
            "email": app.legacy_contact_email or app.contact_email or "",
            "bank_data": {
                "name": app.refund_account_holder_name or "",
                "tax_id": app.refund_account_holder_tax_id or "",
                "bank": app.refund_bank_name or "",
                "agency": app.refund_branch_number or "",
                "account": app.refund_bank_account_number or "",
                "type": app.get_refund_bank_account_type_display() or "",
            },
            "wants_refund_receipt": app.wants_refund_receipt,
            "refund_receipt_details": app.refund_receipt_details or "",
            "refund_status": refund.get_status_display() if refund else "",
            "refund_amount": refund.amount if refund else Decimal("0.00"),
            "modality_credit": credit,
            "fees": fee_cells,
        }

    def _fee_cell_text(self, cell: dict[str, Any]) -> str:
        if cell["amount"] is None:
            return "Não Emitido"
        pieces = [f"R$ {_fmt_money(cell['amount'])}", cell["status"]]
        if cell["method"]:
            pieces.append(PaymentInstrument.Method(cell["method"]).label)
        if cell["manual"]:
            pieces.append("Manual")
        if cell["superseded"]:
            pieces.append("Substituído")
        return " — ".join(pieces)

    def _export_rows(self, term: Any = None) -> list[list[str]]:
        rows = self.build_financial_report_data(term=term)
        export: list[list[str]] = []
        for row in rows:
            bank = row["bank_data"]
            fees = row["fees"]
            export.append(
                [
                    row["protocol"],
                    row["modality"],
                    row["candidate"],
                    row["tax_id"],
                    row["email"],
                    bank["name"],
                    bank["tax_id"],
                    bank["bank"],
                    bank["agency"],
                    bank["account"],
                    bank["type"],
                    "Sim" if row["wants_refund_receipt"] else "Não",
                    row["refund_receipt_details"],
                    self._fee_cell_text(
                        fees[FeeRequirement.FeeType.APPLICATION_FEE.value]
                    ),
                    self._fee_cell_text(fees[FeeRequirement.FeeType.PROJECT_FEE.value]),
                    self._fee_cell_text(
                        fees[FeeRequirement.FeeType.SUPPLEMENT_FEE.value]
                    ),
                ]
            )
        return export

    def _export_filename(self, term: Any, extension: str) -> str:
        if term is not None:
            return f"relatorio_financeiro_{term.year}_{term.period}.{extension}"
        return f"relatorio_financeiro.{extension}"

    def export_financial_csv(self, term: Any = None) -> HttpResponse:
        """Exporta o relatório financeiro em CSV com ``;`` e BOM UTF-8 (TS-REP-004)."""
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = self._export_filename(term, "csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";", lineterminator="\n")
        writer.writerow(FINANCIAL_EXPORT_HEADERS)
        for row in self._export_rows(term=term):
            writer.writerow(row)
        return response

    def export_financial_xlsx(self, term: Any = None) -> HttpResponse:
        """Exporta o relatório financeiro em XLSX (fallback TSV se openpyxl ausente - TS-REP-005)."""
        try:
            import openpyxl  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError:
            return self._export_financial_tsv_fallback(term=term)
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Financeiro"
        worksheet.append(FINANCIAL_EXPORT_HEADERS)
        for row in self._export_rows(term=term):
            worksheet.append(row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
        filename = self._export_filename(term, "xlsx")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _export_financial_tsv_fallback(self, term: Any = None) -> HttpResponse:
        buffer = io.StringIO()
        buffer.write("\ufeff")
        writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
        writer.writerow(FINANCIAL_EXPORT_HEADERS)
        for row in self._export_rows(term=term):
            writer.writerow(row)
        response = HttpResponse(
            buffer.getvalue(), content_type="text/tab-separated-values; charset=utf-8"
        )
        filename = self._export_filename(term, "tsv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    # ---- Auditoria ----

    def build_audit_report_data(self, term: Any = None) -> list[dict[str, Any]]:
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
        if term is not None:
            applications = applications.filter(term=term)
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
