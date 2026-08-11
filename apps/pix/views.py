import json
from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from applications.models import ServiceApplication
from payments.models import FeeRequirement
from users.models import User

from .models import PixPaymentInstrument
from .services import PixPaymentService

_pix_service = PixPaymentService()


@csrf_exempt
@require_POST
def pix_webhook(request: HttpRequest) -> HttpResponse:
    """POST /webhooks/pix/ — recebe entregas de webhook do gateway Pix."""
    token = request.headers.get("X-Token")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "payload inválido"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "payload deve ser um objeto JSON"}, status=400)
    event = _pix_service.process_webhook_payload(raw_payload=payload, token=token)
    if not event.token_valid:
        return JsonResponse({"error": "token inválido"}, status=401)
    return JsonResponse({"processed": True})


class BasePixView(LoginRequiredMixin, View):
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


class GeneratePixView(BasePixView):
    """Candidato gera um novo Pix para a taxa da inscrição."""

    template_name = "payments/fee_payment.html"

    def post(self, request: HttpRequest, protocol: str):
        application = self.get_application(request, protocol)
        fee = self.get_fee(application)
        if fee is None:
            return redirect("payments:fee_payment", protocol=application.protocol)
        try:
            _pix_service.generate_pix_for_fee(
                fee_requirement=fee,
                created_by=cast(User, request.user),
            )
        except Exception:
            return redirect("payments:fee_payment", protocol=application.protocol)
        return redirect("pix:detail", protocol=application.protocol)


class PixDetailView(BasePixView):
    """Exibe o QR Code Pix e o payload copia-e-cola para o candidato."""

    template_name = "pix/pix_detail.html"

    def get(self, request: HttpRequest, protocol: str):
        application = self.get_application(request, protocol)
        pix = (
            PixPaymentInstrument.objects.select_related(
                "qr_code_image_asset", "payment_instrument__fee_requirement"
            )
            .filter(payment_instrument__fee_requirement__application=application)
            .order_by("-created_at")
            .first()
        )
        return render(
            request,
            self.template_name,
            {"application": application, "pix": pix},
        )


class PixQrCodeImageView(LoginRequiredMixin, View):
    """Serve a imagem do QR Code armazenada como FileAsset."""

    def get(self, request: HttpRequest, pix_id: int):
        pix = get_object_or_404(
            PixPaymentInstrument.objects.select_related("qr_code_image_asset"),
            pk=pix_id,
        )
        asset = pix.qr_code_image_asset
        if asset is None:
            return HttpResponse(status=404)
        from django.core.files.storage import default_storage

        return FileResponse(
            default_storage.open(asset.storage_key, "rb"),
            content_type=asset.content_type or "image/png",
        )
