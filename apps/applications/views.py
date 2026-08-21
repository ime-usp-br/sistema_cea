from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from payments.models import PaymentInstrument
from payments.services import ModalityChangeService
from terms.models import AcademicTerm
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
            return ServiceApplication.objects.select_related(
                "term", "owner", "project_screening", "consultation_meeting"
            ).prefetch_related(
                "catalog_selections__option",
                "attachments__file_asset",
                "events__actor",
                "audit_submissions__file_asset",
                "audit_submissions__submitted_by",
                "audit_submissions__reviews__reviewer",
                "audit_submissions__resolutions__decided_by",
                "audit_submissions__resolutions__target_term",
                "fee_requirements__payment_instruments",
                "refund_requests",
            )
        return (
            ServiceApplication.objects.filter(owner=user)
            .select_related("term", "owner", "project_screening", "consultation_meeting")
            .prefetch_related(
                "catalog_selections__option",
                "attachments__file_asset",
                "events__actor",
                "audit_submissions__file_asset",
                "audit_submissions__submitted_by",
                "fee_requirements__payment_instruments",
                "refund_requests",
            )
        )

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


class ApplicationListView(RoleRequiredMixin, View):
    """Secretaria/administrador visualiza todas as inscrições (visão geral).

    Alinhada ao legado: exibe protocolo, data, modalidade, nome, e-mail, status,
    taxas com status de cobrança e ações (ver, PDF, transferir, mudar modalidade,
    excluir). Aceita o parâmetro ``term`` para filtrar por período letivo.
    """

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "applications/application_list.html"

    def get(self, request):
        terms = list(AcademicTerm.objects.all())
        term_id = request.GET.get("term") or request.GET.get("semester_id")

        applications = (
            ServiceApplication.objects.select_related("term")
            .prefetch_related("fee_requirements__payment_instruments")
            .order_by("-created_at")
        )
        if term_id:
            applications = applications.filter(term_id=term_id)

        rows = [self._row(app) for app in applications]
        selected_term = next(
            (t for t in terms if str(t.pk) == str(term_id)), None
        ) if term_id else None

        return render(
            request,
            self.template_name,
            {
                "rows": rows,
                "terms": terms,
                "selected_term_id": term_id,
                "selected_term": selected_term,
            },
        )

    @staticmethod
    def _fee_status(fee) -> str:
        instruments = list(fee.payment_instruments.all())
        if fee.is_waived:
            return "Dispensada"
        if fee.is_paid:
            return "Pago"
        if any(
            item.state in (PaymentInstrument.State.ACTIVE, PaymentInstrument.State.CREATED)
            for item in instruments
        ):
            return "Emitido"
        if instruments:
            return "Cancelado"
        return "Não Emitido"

    @classmethod
    def _row(cls, application: ServiceApplication) -> dict:
        return {
            "application": application,
            "fees_info": [
                {
                    "label": fee.get_fee_type_display(),
                    "amount": fee.amount,
                    "status": cls._fee_status(fee),
                }
                for fee in application.fee_requirements.all()
            ],
        }


class ApplicationModalityChangeView(RoleRequiredMixin, View):
    """Secretaria muda a modalidade de uma inscrição (Projeto <-> Consulta)."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request, protocol: str):
        application = get_object_or_404(ServiceApplication, protocol=protocol)
        user = cast(User, request.user)
        service = ModalityChangeService()
        if application.modality == ServiceApplication.Modality.PROJECT:
            service.convert_to_consultation(application=application, decided_by=user)
        else:
            service.convert_to_project(application=application, decided_by=user)
        return redirect(reverse("applications:list"))


class ApplicationDeleteView(RoleRequiredMixin, View):
    """Secretaria exclui logicamente (soft delete) uma inscrição (TS-XXX)."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request, protocol: str):
        application = get_object_or_404(ServiceApplication, protocol=protocol)
        application.soft_delete()
        return redirect(reverse("applications:list"))


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
