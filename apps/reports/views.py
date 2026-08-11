from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views import View

from users.models import User

from .services import ReportService

_service = ReportService()


class RoleRequiredMixin(LoginRequiredMixin):
    """Exige que o usuário autenticado possua um dos papéis listados."""

    allowed_roles: frozenset[str] = frozenset()

    def dispatch(self, request, *args, **kwargs):
        user = cast(User, request.user)
        if not user.is_authenticated:
            return self.handle_no_permission()
        if user.role not in self.allowed_roles and not user.is_superuser:
            raise PermissionDenied("Você não tem permissão para acessar esta área.")
        return super().dispatch(request, *args, **kwargs)


class FinancialReportView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "reports/financial_report.html"

    def get(self, request):
        rows = _service.build_financial_report_data()
        return render(request, self.template_name, {"rows": rows})


class FinancialExportCsvView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def get(self, request):
        return _service.export_financial_csv()


class FinancialExportXlsxView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def get(self, request):
        return _service.export_financial_xlsx()


class AuditReportView(RoleRequiredMixin, View):
    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "reports/audit_report.html"

    def get(self, request):
        rows = _service.build_audit_report_data()
        return render(request, self.template_name, {"rows": rows})
