from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from payments.models import PaymentInstrument
from payments.services import ModalityChangeService, fee_status_label
from terms.models import AcademicTerm
from terms.utils import resolve_term, term_filter_id
from users.mixins import RoleRequiredMixin
from users.models import User

from .forms import ApplicationForm
from .models import ApplicationEvent, ServiceApplication
from .services import ApplicationSubmissionService, TermTransferService


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
        if (
            user.role
            in {
                User.Role.SECRETARIAT,
                User.Role.ADMINISTRATOR,
                User.Role.TEACHER,
            }
            or user.is_superuser
        ):
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
        user = cast(User, self.request.user)
        # CPF e dados financeiros: visíveis ao dono, Secretaria e Admin;
        # ocultos ao Docente (ARCHITECTURE.md §7.3/§38.2).
        context["can_view_financial"] = (
            user.is_superuser
            or user.role in {User.Role.SECRETARIAT, User.Role.ADMINISTRATOR}
            or (user.role == User.Role.CANDIDATE and application.owner_id == user.pk)
        )
        # Catálogo agrupado por categoria (Vínculo/Finalidade/Agência/Área).
        catalog: dict[str, list[str]] = {}
        for selection in application.catalog_selections.all():
            value = selection.option.label
            if selection.other_text:
                value = f"{value} — {selection.other_text}"
            catalog.setdefault(selection.option.category, []).append(value)
        context["catalog_by_category"] = catalog

        # Boletos da inscrição para as ações administrativas (Gap D).
        from bank_slips.models import BankSlipPaymentInstrument

        today = timezone.localdate()
        financial_rows = []
        for fee in application.fee_requirements.all():
            instruments = []
            for instrument in fee.payment_instruments.all():
                slip = BankSlipPaymentInstrument.objects.filter(
                    payment_instrument=instrument
                ).first()
                already_paid = instrument.state in (
                    PaymentInstrument.State.PAID,
                    PaymentInstrument.State.MANUAL_CONFIRMED,
                )
                can_confirm = bool(
                    slip is not None
                    and slip.due_date is not None
                    and slip.due_date <= today
                    and not already_paid
                )
                instruments.append(
                    {
                        "instrument": instrument,
                        "slip": slip,
                        "can_confirm": can_confirm,
                    }
                )
            financial_rows.append({"fee": fee, "instruments": instruments})
        context["financial_rows"] = financial_rows

        context["slips"] = list(
            BankSlipPaymentInstrument.objects.select_related("payment_instrument")
            .filter(
                payment_instrument__fee_requirement__application=application
            )
            .order_by("-created_at")
        )
        return context


def _schedule_url_name(application: ServiceApplication) -> str | None:
    """Rota de agendamento indicada para o status atual (atalho do legado)."""
    if (
        application.lifecycle_status
        == ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
    ):
        return "meetings:screening_schedule"
    if (
        application.lifecycle_status
        == ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
    ):
        return "meetings:consultation_schedule"
    return None


class ApplicationListView(RoleRequiredMixin, View):
    """Secretaria/administrador visualiza todas as inscrições (visão geral).

    Alinhada ao legado: exibe protocolo, data, modalidade, nome, e-mail, status,
    taxas com status de cobrança e ações (ver, PDF, transferir, mudar modalidade,
    excluir). Filtra por período letivo com default no semestre atual.
    """

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "applications/application_list.html"

    def get(self, request):
        terms = list(AcademicTerm.objects.all())
        raw_term = term_filter_id(request)
        selected_term = None if raw_term == "all" else resolve_term(request)

        applications = (
            ServiceApplication.objects.select_related("term")
            .prefetch_related("fee_requirements__payment_instruments")
            .order_by("-created_at")
        )
        if selected_term is not None:
            applications = applications.filter(term=selected_term)

        rows = [self._row(app) for app in applications]

        if selected_term is not None:
            selected_term_id: str | None = str(selected_term.pk)
        elif raw_term == "all":
            selected_term_id = "all"
        else:
            selected_term_id = None

        return render(
            request,
            self.template_name,
            {
                "rows": rows,
                "terms": terms,
                "selected_term_id": selected_term_id,
                "selected_term": selected_term,
                "show_all": raw_term == "all",
            },
        )

    @staticmethod
    def _fee_status(fee) -> str:
        return fee_status_label(fee)

    @classmethod
    def _row(cls, application: ServiceApplication) -> dict:
        fees_info = []
        show_generate_slip = False
        for fee in application.fee_requirements.all():
            status = cls._fee_status(fee)
            if not fee.is_waived and status != "Pago":
                show_generate_slip = True
            fees_info.append(
                {
                    "label": fee.get_fee_type_display(),
                    "amount": fee.amount,
                    "status": status,
                }
            )
        return {
            "application": application,
            "fees_info": fees_info,
            "schedule_url_name": _schedule_url_name(application),
            "show_generate_slip": show_generate_slip,
        }


class EventListView(RoleRequiredMixin, View):
    """Histórico de eventos das inscrições, filtrável por semestre (legado)."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "applications/event_list.html"

    def get(self, request):
        terms = list(AcademicTerm.objects.all())
        raw_term = term_filter_id(request)
        selected_term = None if raw_term == "all" else resolve_term(request)

        events = (
            ApplicationEvent.objects.select_related("application", "actor")
            .order_by("-occurred_at")
        )
        if selected_term is not None:
            events = events.filter(application__term=selected_term)

        return render(
            request,
            self.template_name,
            {
                "events": events,
                "terms": terms,
                "selected_term": selected_term,
                "selected_term_id": (
                    str(selected_term.pk)
                    if selected_term is not None
                    else ("all" if raw_term == "all" else None)
                ),
            },
        )


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


class ApplicationDeletedListView(RoleRequiredMixin, View):
    """Lixeira: inscrições com exclusão lógica, com restauração (paridade legado)."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "applications/application_deleted_list.html"

    def get(self, request):
        terms = list(AcademicTerm.objects.all())
        raw_term = term_filter_id(request)
        selected_term = None if raw_term == "all" else resolve_term(request)

        applications = (
            ServiceApplication.all_objects.filter(soft_deleted_at__isnull=False)
            .select_related("term", "owner")
            .order_by("-soft_deleted_at")
        )
        if selected_term is not None:
            applications = applications.filter(term=selected_term)

        return render(
            request,
            self.template_name,
            {
                "applications": applications,
                "terms": terms,
                "selected_term": selected_term,
                "selected_term_id": (
                    str(selected_term.pk)
                    if selected_term is not None
                    else ("all" if raw_term == "all" else None)
                ),
            },
        )


class ApplicationRestoreView(RoleRequiredMixin, View):
    """Restaura uma inscrição previamente excluída (soft delete)."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})

    def post(self, request, protocol: str):
        application = get_object_or_404(
            ServiceApplication.all_objects, protocol=protocol
        )
        application.restore()
        ApplicationEvent.objects.create(
            application=application,
            event_code="application.restored",
            actor=cast(User, request.user),
            description="Inscrição restaurada pela Secretaria.",
        )
        return redirect(reverse("applications:deleted_list"))


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
