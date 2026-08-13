from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from users.models import User

from .forms import ApplicationForm
from .models import ServiceApplication
from .services import ApplicationSubmissionService, TermTransferService


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


class CandidateDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "applications/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        owner = cast(User, self.request.user)
        context["applications"] = ServiceApplication.objects.filter(owner=owner)
        return context


class CreateApplicationView(LoginRequiredMixin, FormView):
    template_name = "applications/application_form.html"
    form_class = ApplicationForm

    def form_valid(self, form):
        service = ApplicationSubmissionService()
        owner = cast(User, self.request.user)
        application = service.create_application(
            term=form.cleaned_data["term"],
            owner=owner,
            modality=form.cleaned_data["modality"],
            researcher_name=form.cleaned_data["researcher_name"],
            contact_email=form.cleaned_data["contact_email"],
            contact_phone=form.cleaned_data.get("contact_phone"),
            has_whatsapp=form.cleaned_data.get("has_whatsapp", False),
            tax_id=form.cleaned_data.get("tax_id"),
            institution_name=form.cleaned_data.get("institution_name"),
            course_name=form.cleaned_data.get("course_name"),
            mentor_name=form.cleaned_data.get("mentor_name"),
            project_title=form.cleaned_data.get("project_title"),
            context_summary=form.cleaned_data.get("context_summary"),
            general_objectives=form.cleaned_data.get("general_objectives"),
            variables_and_measurements=form.cleaned_data.get("variables_and_measurements"),
            contextual_factors=form.cleaned_data.get("contextual_factors"),
            sampling_and_limitations=form.cleaned_data.get("sampling_and_limitations"),
            data_management_plan=form.cleaned_data.get("data_management_plan"),
            expected_results=form.cleaned_data.get("expected_results"),
            expected_support=form.cleaned_data.get("expected_support"),
            data_already_collected=form.cleaned_data.get("data_already_collected"),
            data_use_authorization_accepted=form.cleaned_data.get("data_use_authorization_accepted", False),
            mentor_declaration_accepted=form.cleaned_data.get("mentor_declaration_accepted", False),
            wants_refund_receipt=bool(form.cleaned_data.get("wants_refund_receipt")),
            refund_receipt_details=form.cleaned_data.get("refund_receipt_details"),
            refund_account_holder_name=form.cleaned_data.get("refund_account_holder_name"),
            refund_account_holder_tax_id=form.cleaned_data.get("refund_account_holder_tax_id"),
            refund_bank_name=form.cleaned_data.get("refund_bank_name"),
            refund_branch_number=form.cleaned_data.get("refund_branch_number"),
            refund_bank_account_number=form.cleaned_data.get("refund_bank_account_number"),
            refund_bank_account_type=form.cleaned_data.get("refund_bank_account_type"),
            catalog_option_ids=[option.pk for option in form.cleaned_data.get("catalog_options", [])],
            catalog_other_text=form.cleaned_data.get("catalog_other_text"),
            attachments=form.cleaned_data.get("attachments") or [],
        )
        return redirect(reverse("applications:detail", args=[application.protocol]))

    def form_invalid(self, form):
        return super().form_invalid(form)


class ApplicationDetailView(LoginRequiredMixin, DetailView):
    model = ServiceApplication
    template_name = "applications/application_detail.html"
    slug_field = "protocol"
    slug_url_kwarg = "protocol"

    def get_queryset(self):
        user = cast(User, self.request.user)
        if user.role in {User.Role.SECRETARIAT, User.Role.ADMINISTRATOR} or user.is_superuser:
            return ServiceApplication.objects.all()
        return ServiceApplication.objects.filter(owner=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object
        # Boletos da inscrição para as ações administrativas (Gap D).
        from bank_slips.models import BankSlipPaymentInstrument

        context["slips"] = list(
            BankSlipPaymentInstrument.objects.select_related("payment_instrument")
            .filter(
                payment_instrument__fee_requirement__application=application
            )
            .order_by("-created_at")
        )
        return context


class TransferSemesterView(RoleRequiredMixin, View):
    """Secretaria transfere uma inscrição para o próximo semestre (TS-TRM-006)."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request, protocol: str):
        application = get_object_or_404(ServiceApplication, protocol=protocol)
        user = cast(User, request.user)
        TermTransferService().transfer_to_next_semester(
            application, decided_by=user
        )
        return redirect(reverse("applications:detail", args=[protocol]))
