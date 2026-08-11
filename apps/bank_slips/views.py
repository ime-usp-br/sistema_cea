from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
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
