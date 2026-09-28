from typing import cast

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from applications.models import ServiceApplication
from bank_slips.services import BankSlipPaymentService
from pix.services import PixPaymentService
from terms.models import AcademicTerm
from terms.utils import resolve_term
from users.mixins import RoleRequiredMixin
from users.models import User

from .forms import ManualPaymentConfirmationForm, PaymentMethodForm, RefundRequestForm
from .models import FeeRequirement, PaymentInstrument, RefundRequest
from .services import (
    FeeSelectionService,
    ManualPaymentService,
    ModalityChangeService,
    OverdueBillingService,
    PendingPaymentService,
    RefundRequestService,
)

_fee_service = ModalityChangeService()
_manual_service = ManualPaymentService()
_refund_service = RefundRequestService()
_overdue_service = OverdueBillingService()
_pending_service = PendingPaymentService()
_fee_selection = FeeSelectionService()


def _parse_fee_id(raw: object) -> int | None:
    """Converte o id da taxa recebido por GET/POST em int (ou None)."""
    if raw is None:
        return None
    text = str(raw).strip()
    return int(text) if text.isdigit() else None


class FeePaymentView(LoginRequiredMixin, View):
    """Candidato visualiza a taxa e escolhe a forma de pagamento (Pix/Boleto)."""

    template_name = "payments/fee_payment.html"

    def get_application(self, request, protocol: str) -> ServiceApplication:
        user = cast(User, request.user)
        return get_object_or_404(ServiceApplication, protocol=protocol, owner=user)

    def get_fee(
        self, application: ServiceApplication, fee_id: int | None = None
    ) -> FeeRequirement | None:
        return _fee_selection.select_fee(application, fee_id)

    def get(self, request, protocol: str):
        application = self.get_application(request, protocol)
        fee = self.get_fee(application, _parse_fee_id(request.GET.get("fee")))
        fees = _fee_selection.ordered_fees(application)
        if fee is None:
            return render(
                request,
                self.template_name,
                {"application": application, "fee": None, "fees": fees, "form": None},
            )
        form = PaymentMethodForm()
        return render(
            request,
            self.template_name,
            {"application": application, "fee": fee, "fees": fees, "form": form},
        )

    def post(self, request, protocol: str):
        application = self.get_application(request, protocol)
        fee_id = _parse_fee_id(request.POST.get("fee_id") or request.GET.get("fee"))
        fee = self.get_fee(application, fee_id)
        fees = _fee_selection.ordered_fees(application)
        if fee is None:
            return redirect("payments:fee_payment", protocol=application.protocol)
        if fee.is_paid:
            return redirect(
                f"{reverse('payments:fee_payment', kwargs={'protocol': application.protocol})}"
                f"?fee={fee.pk}"
            )
        form = PaymentMethodForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"application": application, "fee": fee, "fees": fees, "form": form},
                status=400,
            )
        try:
            # Gera o instrumento e já a cobrança externa (QR Code Pix ou boleto)
            # na mesma ação: o candidato escolheu o método aqui mesmo.
            if form.cleaned_data["method"] == PaymentInstrument.Method.PIX:
                PixPaymentService().generate_pix_for_fee(
                    fee_requirement=fee,
                    created_by=cast(User, request.user),
                )
                return redirect("pix:detail", protocol=application.protocol)
            BankSlipPaymentService().generate_bank_slip_for_fee(
                fee_requirement=fee,
                created_by=cast(User, request.user),
            )
            return redirect("bank_slips:detail", protocol=application.protocol)
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                {"application": application, "fee": fee, "fees": fees, "form": form},
                status=400,
            )


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


class RefundRequestCreateView(LoginRequiredMixin, View):
    """Candidato solicita um reembolso para a própria inscrição."""

    template_name = "payments/refund_request_form.html"

    def get_application(self, protocol: str) -> ServiceApplication:
        user = cast(User, self.request.user)
        return get_object_or_404(ServiceApplication, protocol=protocol, owner=user)

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
        # O candidato não acessa a lista de reembolsos (área da Secretaria):
        # volta à própria inscrição, onde vê a solicitação registrada.
        return redirect("applications:detail", protocol=application.protocol)


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


class OverdueBillingListView(RoleRequiredMixin, View):
    """Painel de inadimplência: boletos vencidos agrupados por inscrição.

    Porta do ``ApplicationController@overdueIndex`` do sistema legado, incluindo
    filtro por semestre (default = atual), seleção em massa e histórico de
    cobrança por linha.
    """

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "payments/overdue_list.html"

    def get(self, request):
        terms = list(AcademicTerm.objects.all())
        raw_term = request.GET.get("term") or request.GET.get("semester_id")
        selected_term = None if raw_term == "all" else resolve_term(request)
        rows = _overdue_service.build_overdue_rows(term=selected_term)
        return render(
            request,
            self.template_name,
            {
                "rows": rows,
                "terms": terms,
                "selected_term": selected_term,
                "selected_term_id": (
                    str(selected_term.pk)
                    if selected_term is not None
                    else ("all" if raw_term == "all" else None)
                ),
            },
        )


class OverdueReminderView(RoleRequiredMixin, View):
    """Secretaria dispara e-mails de cobrança para os boletos vencidos selecionados.

    Porta do ``ApplicationController@sendOverdueReminders`` do sistema legado.
    """

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request):
        user = cast(User, request.user)
        raw_ids = request.POST.getlist("slip_ids")
        slip_ids = [int(pk) for pk in raw_ids if pk.isdigit()]
        _overdue_service.send_overdue_reminders(actor=user, slip_ids=slip_ids or None)
        return redirect("payments:overdue_list")


class PendingPaymentsListView(RoleRequiredMixin, View):
    """Secretaria lista inscrições com taxas pendentes de pagamento."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "payments/pending_payments.html"

    def get(self, request):
        rows = _pending_service.list_pending_applications()
        return render(request, self.template_name, {"rows": rows})


class SimulatePaymentView(LoginRequiredMixin, View):
    """Confirma um pagamento localmente em desenvolvimento (T6/E2E).

    Só existe com ``DEBUG=True``; permite fechar o fluxo no navegador sem
    depender do webhook de retorno da USP. A geração continua no gateway dev
    real — apenas a confirmação é simulada.
    """

    def post(self, request, instrument_id: int):
        if not settings.DEBUG:
            raise Http404("Simulação de pagamento indisponível.")
        instrument = get_object_or_404(
            PaymentInstrument.objects.select_related("fee_requirement__application"),
            pk=instrument_id,
        )
        user = cast(User, request.user)
        application = instrument.fee_requirement.application
        is_staff = user.is_superuser or user.role in {
            User.Role.SECRETARIAT,
            User.Role.ADMINISTRATOR,
        }
        if not is_staff and application.owner_id != user.pk:
            raise PermissionDenied("Você não tem acesso a este pagamento.")

        if instrument.method == PaymentInstrument.Method.PIX:
            pix = getattr(instrument, "pix_instrument", None)
            if pix is None:
                raise Http404("Pix não encontrado para este instrumento.")
            PixPaymentService().simulate_payment(pix)
            return redirect("pix:detail", protocol=application.protocol)
        if instrument.method == PaymentInstrument.Method.BANK_SLIP:
            slip = getattr(instrument, "bank_slip_instrument", None)
            if slip is None:
                raise Http404("Boleto não encontrado para este instrumento.")
            BankSlipPaymentService().simulate_payment(slip)
            return redirect("bank_slips:detail", protocol=application.protocol)
        raise Http404("Método de pagamento não simulável.")
