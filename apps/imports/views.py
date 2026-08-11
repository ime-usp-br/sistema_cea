from typing import Any, cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from users.models import User

from .forms import ClaimConfirmForm, ClaimRequestForm, ManualApprovalForm
from .models import LegacyOwnershipClaim
from .services import LegacyClaimError, LegacyClaimService

_service = LegacyClaimService()


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


class ClaimRequestView(LoginRequiredMixin, View):
    """Candidato inicia o resgate de uma inscrição importada."""

    template_name = "imports/claim_request.html"

    def get(self, request):
        form = ClaimRequestForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = ClaimRequestForm(request.POST)
        if not form.is_valid():
            return render(
                request, self.template_name, {"form": form}, status=400
            )
        try:
            claim, _token = _service.request_claim(
                user=cast(User, request.user),
                protocol=form.cleaned_data.get("protocol") or "",
                contact_email_or_tax_id=form.cleaned_data["contact_email_or_tax_id"],
            )
        except LegacyClaimError as exc:
            form.add_error(None, str(exc))
            return render(
                request, self.template_name, {"form": form}, status=400
            )
        request.session["pending_claim_id"] = claim.pk
        return redirect("imports:claim_confirm")


class ClaimConfirmView(LoginRequiredMixin, View):
    """Candidato confirma o código recebido por e-mail."""

    template_name = "imports/claim_confirm.html"

    def get_claim(self, request) -> LegacyOwnershipClaim:
        claim_id = request.session.get("pending_claim_id")
        if not claim_id:
            return None  # type: ignore[return-value]
        return get_object_or_404(
            LegacyOwnershipClaim, pk=claim_id, user=request.user
        )

    def get(self, request):
        claim = self.get_claim(request)
        if claim is None:
            return redirect("imports:claim_request")
        form = ClaimConfirmForm()
        return render(
            request, self.template_name, {"form": form, "claim": claim}
        )

    def post(self, request):
        claim = self.get_claim(request)
        if claim is None:
            return redirect("imports:claim_request")
        form = ClaimConfirmForm(request.POST)
        if not form.is_valid():
            return render(
                request, self.template_name, {"form": form, "claim": claim}, status=400
            )
        try:
            _service.confirm_claim(
                user=cast(User, request.user),
                claim_id=claim.pk,
                code=form.cleaned_data["code"],
            )
        except LegacyClaimError as exc:
            form.add_error(None, str(exc))
            return render(
                request, self.template_name, {"form": form, "claim": claim}, status=400
            )
        request.session.pop("pending_claim_id", None)
        return redirect("applications:dashboard")


class ClaimQueueView(RoleRequiredMixin, View):
    """Fila de solicitações de resgate para a secretaria."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "imports/claim_queue.html"

    def get(self, request):
        claims = (
            LegacyOwnershipClaim.objects.select_related("application", "user")
            .exclude(status=LegacyOwnershipClaim.Status.VERIFIED)
            .order_by("created_at")
        )
        return render(request, self.template_name, {"claims": claims})


class ClaimApproveView(RoleRequiredMixin, View):
    """Secretaria aprova manualmente um resgate."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "imports/claim_approve.html"

    def get_claim(self, claim_id: int) -> LegacyOwnershipClaim:
        return get_object_or_404(
            LegacyOwnershipClaim.objects.select_related("application", "user"),
            pk=claim_id,
        )

    def get_context(self, claim: LegacyOwnershipClaim) -> dict[str, Any]:
        return {"claim": claim, "form": ManualApprovalForm(instance=claim)}

    def get(self, request, claim_id: int):
        claim = self.get_claim(claim_id)
        return render(request, self.template_name, self.get_context(claim))

    def post(self, request, claim_id: int):
        claim = self.get_claim(claim_id)
        form = ManualApprovalForm(request.POST, instance=claim)
        if not form.is_valid():
            context = self.get_context(claim)
            context["form"] = form
            return render(request, self.template_name, context, status=400)
        try:
            _service.manually_approve_claim(
                claim=claim,
                secretariat_user=cast(User, request.user),
                note=form.cleaned_data.get("review_note"),
            )
        except LegacyClaimError as exc:
            form.add_error(None, str(exc))
            context = self.get_context(claim)
            context["form"] = form
            return render(request, self.template_name, context, status=400)
        return redirect(reverse("imports:claim_queue"))
