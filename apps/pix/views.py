import json
from typing import cast

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from applications.models import ServiceApplication
from payments.models import FeeRequirement, PaymentInstrument
from payments.services import FeeSelectionService
from users.models import User

from .models import PixPaymentInstrument
from .services import PixPaymentService

_pix_service = PixPaymentService()
_fee_selection = FeeSelectionService()


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
        if (
            user.role in {User.Role.SECRETARIAT, User.Role.ADMINISTRATOR}
            or user.is_superuser
        ):
            return get_object_or_404(ServiceApplication, protocol=protocol)
        return get_object_or_404(ServiceApplication, protocol=protocol, owner=user)

    def get_fee(
        self, application: ServiceApplication, fee_id: int | None = None
    ) -> FeeRequirement | None:
        return _fee_selection.select_fee(application, fee_id)


def _parse_fee_id(raw: object) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return int(text) if text.isdigit() else None


def _latest_relevant_pix(application: ServiceApplication) -> PixPaymentInstrument | None:
    """Pix mais recente que ainda faz sentido mostrar ao candidato.

    Prioriza um Pix ativo/criado (o que o candidato precisa pagar agora). Se
    não houver, devolve o Pix pago mais recente (para exibir o recibo).
    Instrumentos expirados/cancelados são ignorados, permitindo que a tela
    ofereça a geração de um novo Pix.
    """
    base = (
        PixPaymentInstrument.objects.select_related(
            "qr_code_image_asset", "payment_instrument__fee_requirement"
        )
        .filter(payment_instrument__fee_requirement__application=application)
        .order_by("-created_at")
    )
    active = base.filter(
        payment_instrument__state__in=[
            PaymentInstrument.State.ACTIVE,
            PaymentInstrument.State.CREATED,
            PaymentInstrument.State.REQUIRES_REVIEW,
        ]
    ).first()
    if active is not None:
        return active
    return base.filter(
        payment_instrument__state__in=[
            PaymentInstrument.State.PAID,
            PaymentInstrument.State.MANUAL_CONFIRMED,
        ]
    ).first()


class GeneratePixView(BasePixView):
    """Candidato gera um novo Pix para uma taxa da inscrição (D3)."""

    template_name = "payments/fee_payment.html"

    def post(self, request: HttpRequest, protocol: str):
        application = self.get_application(request, protocol)
        fee_id = _parse_fee_id(request.POST.get("fee_id") or request.GET.get("fee"))
        fee = self.get_fee(application, fee_id)
        if fee is None:
            return redirect("payments:fee_payment", protocol=application.protocol)
        try:
            _pix_service.generate_pix_for_fee(
                fee_requirement=fee,
                created_by=cast(User, request.user),
            )
        except Exception as exc:
            messages.error(request, f"Não foi possível gerar o Pix: {exc}")
            return redirect("payments:fee_payment", protocol=application.protocol)
        return redirect("pix:detail", protocol=application.protocol)


class PixCheckView(BasePixView):
    """Consulta o gateway e confirma o Pix sem depender do webhook."""

    def post(self, request: HttpRequest, protocol: str):
        application = self.get_application(request, protocol)
        pix = _latest_relevant_pix(application)
        if pix is None:
            messages.warning(request, "Nenhum Pix foi encontrado para esta inscrição.")
            return redirect("pix:detail", protocol=application.protocol)
        try:
            _pix_service.check_pix_status(pix, verify=True)
        except Exception as exc:
            messages.error(
                request,
                f"Não foi possível consultar o Pix agora: {exc}",
            )
        else:
            pix.refresh_from_db()
            if pix.payment_instrument.state in {
                PaymentInstrument.State.PAID,
                PaymentInstrument.State.MANUAL_CONFIRMED,
            }:
                messages.success(request, "Pagamento Pix confirmado com sucesso.")
            else:
                messages.info(
                    request,
                    "O pagamento ainda não consta como confirmado no gateway.",
                )
        return redirect("pix:detail", protocol=application.protocol)


class PixDetailView(BasePixView):
    """Exibe o QR Code Pix e o payload copia-e-cola para o candidato."""

    template_name = "pix/pix_detail.html"

    def get(self, request: HttpRequest, protocol: str):
        application = self.get_application(request, protocol)
        pix = _latest_relevant_pix(application)
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
