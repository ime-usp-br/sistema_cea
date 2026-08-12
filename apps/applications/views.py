from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView

from users.models import User

from .forms import ApplicationForm
from .models import ServiceApplication
from .services import ApplicationSubmissionService


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
        owner = cast(User, self.request.user)
        return ServiceApplication.objects.filter(owner=owner)
