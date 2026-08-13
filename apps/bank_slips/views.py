import contextlib
from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from applications.models import ServiceApplication
from payments.models import FeeRequirement
from users.models import User

from .models import BankSlipPaymentInstrument
from .services import BankSlipPaymentService

_slip_service = BankSlipPaymentService()


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


class BaseBankSlipView(LoginRequiredMixin, View):
    def get_application(self, request: HttpRequest, protocol: str) -> ServiceApplication:
        user = cast(User, request.user)
        return get_object_or_404(ServiceApplication, protocol=protocol, owner=user)

    def get_fee(self, application: ServiceApplication) -> FeeRequirement | None:
        return (
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            )
            .order_by("-created_at")
            .first()
        )


class GenerateBankSlipView(BaseBankSlipView):
    """Candidato gera um boleto para a taxa da inscrição."""

    def post(self, request: HttpRequest, protocol: str):
        application = self.get_application(request, protocol)
        fee = self.get_fee(application)
        if fee is None:
            return redirect("payments:fee_payment", protocol=application.protocol)
        try:
            _slip_service.generate_bank_slip_for_fee(
                fee_requirement=fee,
                created_by=cast(User, request.user),
            )
        except Exception:
            return redirect("payments:fee_payment", protocol=application.protocol)
        return redirect("bank_slips:detail", protocol=application.protocol)


class BankSlipDetailView(BaseBankSlipView):
    """Exibe o boleto gerado e o link para download do PDF."""

    template_name = "bank_slips/bank_slip_detail.html"

    def get(self, request: HttpRequest, protocol: str):
        application = self.get_application(request, protocol)
        slip = (
            BankSlipPaymentInstrument.objects.select_related(
                "pdf_asset", "payment_instrument__fee_requirement"
            )
            .filter(payment_instrument__fee_requirement__application=application)
            .order_by("-created_at")
            .first()
        )
        return render(
            request,
            self.template_name,
            {"application": application, "slip": slip},
        )


class BankSlipDownloadPdfView(LoginRequiredMixin, View):
    """Baixa o PDF do boleto."""

    def get(self, request: HttpRequest, slip_id: int):
        slip = get_object_or_404(
            BankSlipPaymentInstrument.objects.select_related("pdf_asset"),
            pk=slip_id,
        )
        asset = _slip_service.fetch_pdf(slip)
        if asset is None:
            raise Http404("PDF do boleto indisponível.")
        return FileResponse(
            default_storage.open(asset.storage_key, "rb"),
            content_type="application/pdf",
        )


class AdminRegenerateBankSlipView(RoleRequiredMixin, View):
    """Secretaria reemite um boleto e notifica o candidato.

    Porta do ``ApplicationController@regenerateBoleto`` do sistema legado:
    permite à Secretaria regenerar forçadamente um boleto e notificar o usuário.
    """

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request: HttpRequest, slip_id: int):
        slip = get_object_or_404(BankSlipPaymentInstrument, pk=slip_id)
        user = cast(User, request.user)
        _slip_service.regenerate_slip(slip, created_by=user)
        protocol = slip.payment_instrument.fee_requirement.application.protocol
        return redirect("applications:detail", protocol=protocol)


class AdminGenerateBankSlipView(RoleRequiredMixin, View):
    """Secretaria força a emissão do boleto primário de uma inscrição.

    Porta do botão "Gerar Boleto (Manual)" do sistema legado (Gap D): permite
    gerar um boleto para uma inscrição que ainda não possui boleto ativo (ex.:
    falha na 1ª geração ou emissão forçada), sem depender de um ``slip_id``
    existente. Reutiliza o boleto ativo se já houver um.
    """

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request: HttpRequest, protocol: str):
        application = get_object_or_404(ServiceApplication, protocol=protocol)
        user = cast(User, request.user)
        fee = (
            application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            )
            .order_by("-created_at")
            .first()
        )
        if fee is not None and not fee.is_paid:
            with contextlib.suppress(Exception):  # noqa: BLE001
                _slip_service.generate_bank_slip_for_fee(
                    fee_requirement=fee, created_by=user
                )
        return redirect("applications:detail", protocol=protocol)
