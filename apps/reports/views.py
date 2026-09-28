from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from applications.models import ServiceApplication
from terms.models import AcademicTerm
from terms.utils import resolve_term
from users.mixins import RoleRequiredMixin
from users.models import User

from .services import ReportService

_service = ReportService()


def _term_context(request) -> dict[str, object]:
    raw_term = request.GET.get("term") or request.GET.get("semester_id")
    selected_term = None if raw_term == "all" else resolve_term(request)
    return {
        "selected_term": selected_term,
        "terms": list(AcademicTerm.objects.all()),
        "selected_term_id": (
            str(selected_term.pk)
            if selected_term is not None
            else ("all" if raw_term == "all" else None)
        ),
    }


class FinancialReportView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "reports/financial_report.html"

    def get(self, request):
        term_context = _term_context(request)
        rows = _service.build_financial_report_data(term=term_context["selected_term"])
        return render(
            request,
            self.template_name,
            {"rows": rows, **term_context},
        )


class FinancialExportCsvView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def get(self, request):
        term_context = _term_context(request)
        return _service.export_financial_csv(term=term_context["selected_term"])


class FinancialExportXlsxView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def get(self, request):
        term_context = _term_context(request)
        return _service.export_financial_xlsx(term=term_context["selected_term"])


class FinancialReportSyncView(RoleRequiredMixin, View):
    """Sincroniza os pagamentos de uma inscrição via gateways (D7 opcional)."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request, protocol: str):
        application = get_object_or_404(ServiceApplication, protocol=protocol)
        try:
            synced = _service.sync_application_payments(application)
        except Exception as exc:  # noqa: BLE001 - falha de gateway devolvida como JSON
            return JsonResponse(
                {"protocol": protocol, "error": str(exc)}, status=502
            )
        return JsonResponse({"protocol": protocol, "synced": synced})


class AuditReportView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "reports/audit_report.html"

    def get(self, request):
        term_context = _term_context(request)
        rows = _service.build_audit_report_data(term=term_context["selected_term"])
        return render(
            request,
            self.template_name,
            {"rows": rows, **term_context},
        )
