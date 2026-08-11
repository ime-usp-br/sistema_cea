from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from applications.models import ServiceApplication
from users.models import User

from .forms import ManualPaymentConfirmationForm, PaymentMethodForm, RefundRequestForm
from .models import FeeRequirement, PaymentInstrument, RefundRequest
from .services import (
    ManualPaymentService,
    ModalityChangeService,
    PaymentOrchestrationService,
    RefundRequestService,
)

_fee_service = ModalityChangeService()
_payment_service = PaymentOrchestrationService()
_manual_service = ManualPaymentService()
_refund_service = RefundRequestService()


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


class FeePaymentView(LoginRequiredMixin, View):
    """Candidato visualiza a taxa e escolhe a forma de pagamento (Pix/Boleto)."""

    template_name = "payments/fee_payment.html"

    def get_application(self, request, protocol: str) -> ServiceApplication:
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

    def get(self, request, protocol: str):
        application = self.get_application(request, protocol)
        fee = self.get_fee(application)
        if fee is None:
            return render(
                request,
                self.template_name,
                {"application": application, "fee": None, "form": None},
            )
        form = PaymentMethodForm()
        return render(
            request,
            self.template_name,
            {"application": application, "fee": fee, "form": form},
        )

    def post(self, request, protocol: str):
        application = self.get_application(request, protocol)
        fee = self.get_fee(application)
        if fee is None:
            return redirect("payments:fee_payment", protocol=application.protocol)
        form = PaymentMethodForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"application": application, "fee": fee, "form": form},
                status=400,
            )
        try:
            _payment_service.create_payment_instrument(
                fee_requirement=fee,
                method=form.cleaned_data["method"],
                created_by=cast(User, request.user),
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                {"application": application, "fee": fee, "form": form},
                status=400,
            )
        return redirect("payments:fee_payment", protocol=application.protocol)


class ManualPaymentConfirmationView(RoleRequiredMixin, View):
    """Secretaria registra a confirmação manual de pagamento."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "payments/manual_confirmation.html"

    def get_instrument(self, instrument_id: int) -> PaymentInstrument:
        return get_object_or_404(
            PaymentInstrument.objects.select_related(
                "fee_requirement__application"
            ),
            pk=instrument_id,
        )

    def get(self, request, instrument_id: int):
        instrument = self.get_instrument(instrument_id)
        form = ManualPaymentConfirmationForm()
        return render(
            request,
            self.template_name,
            {"instrument": instrument, "form": form},
        )

    def post(self, request, instrument_id: int):
        instrument = self.get_instrument(instrument_id)
        form = ManualPaymentConfirmationForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"instrument": instrument, "form": form},
                status=400,
            )
        try:
            _manual_service.confirm_manual_payment(
                instrument=instrument,
                confirmed_by=cast(User, request.user),
                note=form.cleaned_data.get("note") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                {"instrument": instrument, "form": form},
                status=400,
            )
        return redirect("payments:manual_confirmation", instrument_id=instrument.pk)


class RefundRequestListView(RoleRequiredMixin, View):
    """Secretaria lista solicitações de reembolso."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "payments/refund_request_list.html"

    def get(self, request):
        refunds = RefundRequest.objects.select_related("application").order_by("-created_at")
        return render(request, self.template_name, {"refunds": refunds})


class RefundRequestCreateView(RoleRequiredMixin, View):
    """Secretaria solicita um reembolso para uma inscrição."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "payments/refund_request_form.html"

    def get_application(self, protocol: str) -> ServiceApplication:
        return get_object_or_404(ServiceApplication, protocol=protocol)

    def get(self, request, protocol: str):
        application = self.get_application(protocol)
        form = RefundRequestForm()
        return render(
            request,
            self.template_name,
            {"application": application, "form": form},
        )

    def post(self, request, protocol: str):
        application = self.get_application(protocol)
        form = RefundRequestForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"application": application, "form": form},
                status=400,
            )
        try:
            _refund_service.create_refund_request(
                application=application,
                requested_by=cast(User, request.user),
                amount=form.cleaned_data["amount"],
                reason=form.cleaned_data.get("reason") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                {"application": application, "form": form},
                status=400,
            )
        return redirect("payments:refund_list")


class RefundActionView(RoleRequiredMixin, View):
    """Secretaria aprova ou executa um reembolso."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def get(self, request, refund_id: int, action: str):
        refund = get_object_or_404(RefundRequest, pk=refund_id)
        user = cast(User, request.user)
        if action == "approve":
            _refund_service.approve(refund_request=refund, approved_by=user)
        elif action == "execute":
            _refund_service.execute(refund_request=refund, executed_by=user)
        return redirect("payments:refund_list")
