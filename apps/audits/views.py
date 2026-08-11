from typing import Any, cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from applications.models import ServiceApplication
from terms.models import AcademicTerm
from users.models import User

from .forms import DatasetResolutionForm, DatasetReviewForm, DatasetSubmissionForm
from .models import DatasetAuditSubmission
from .services import DatasetAuditService

_service = DatasetAuditService()


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


class DatasetSubmitView(LoginRequiredMixin, View):
    """Candidato envia/corrige os dados para auditoria."""

    template_name = "audits/submission_form.html"

    def get_application(self, request, protocol: str) -> ServiceApplication:
        user = cast(User, request.user)
        return get_object_or_404(ServiceApplication, protocol=protocol, owner=user)

    def get(self, request, protocol: str):
        application = self.get_application(request, protocol)
        form = DatasetSubmissionForm()
        return render(
            request,
            self.template_name,
            {"application": application, "form": form},
        )

    def post(self, request, protocol: str):
        application = self.get_application(request, protocol)
        form = DatasetSubmissionForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"application": application, "form": form},
                status=400,
            )
        try:
            _service.submit_dataset(
                application=application,
                submitted_by=cast(User, request.user),
                channel=form.cleaned_data["channel"],
                uploaded_file=form.cleaned_data.get("file"),
                external_url=form.cleaned_data.get("external_url") or None,
                external_link_declaration=form.cleaned_data.get("external_link_declaration", False),
                note=form.cleaned_data.get("note") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                {"application": application, "form": form},
                status=400,
            )
        return redirect("applications:detail", protocol=application.protocol)


class TeacherReviewQueueView(RoleRequiredMixin, View):
    """Fila de submissões pendentes de análise docente."""

    allowed_roles = frozenset({User.Role.TEACHER, User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "audits/teacher_queue.html"

    def get(self, request):
        submissions = (
            DatasetAuditSubmission.objects.select_related("application", "submitted_by")
            .filter(application__lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW)
            .order_by("-submitted_at")
        )
        return render(request, self.template_name, {"submissions": submissions})


class SubmissionReviewView(RoleRequiredMixin, View):
    """Docente revisa uma submissão específica."""

    allowed_roles = frozenset({User.Role.TEACHER, User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "audits/review_form.html"

    def get_submission(self, submission_id: int) -> DatasetAuditSubmission:
        submission = get_object_or_404(
            DatasetAuditSubmission.objects.select_related("application", "submitted_by").select_related(
                "file_asset"
            ),
            pk=submission_id,
        )
        if submission.application.lifecycle_status != (
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW
        ):
            raise Http404("Submissão não está pendente de análise.")
        return submission

    def get(self, request, submission_id: int):
        submission = self.get_submission(submission_id)
        form = DatasetReviewForm()
        return render(request, self.template_name, {"submission": submission, "form": form})

    def post(self, request, submission_id: int):
        submission = self.get_submission(submission_id)
        form = DatasetReviewForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"submission": submission, "form": form},
                status=400,
            )
        try:
            _service.review_submission(
                submission=submission,
                reviewer=cast(User, request.user),
                outcome=form.cleaned_data["outcome"],
                note=form.cleaned_data.get("note") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                {"submission": submission, "form": form},
                status=400,
            )
        return redirect("audits:teacher_queue")


class RejectedResolutionListView(RoleRequiredMixin, View):
    """Secretaria lista auditorias rejeitadas pendentes de decisão."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "audits/resolution_list.html"

    def get(self, request):
        submissions = (
            DatasetAuditSubmission.objects.select_related("application")
            .filter(
                state=DatasetAuditSubmission.State.REJECTED,
                application__lifecycle_status=(
                    ServiceApplication.LifecycleStatus.DATASET_REJECTED_PENDING_RESOLUTION
                ),
            )
            .order_by("-submitted_at")
        )
        return render(request, self.template_name, {"submissions": submissions})


class SubmissionResolutionView(RoleRequiredMixin, View):
    """Secretaria decide o destino de uma auditoria rejeitada."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})
    template_name = "audits/resolution_form.html"

    def get_submission(self, submission_id: int) -> DatasetAuditSubmission:
        submission = get_object_or_404(
            DatasetAuditSubmission.objects.select_related("application"),
            pk=submission_id,
        )
        if submission.application.lifecycle_status != (
            ServiceApplication.LifecycleStatus.DATASET_REJECTED_PENDING_RESOLUTION
        ):
            raise Http404("Submissão não está pendente de decisão administrativa.")
        return submission

    def get_context(self, submission: DatasetAuditSubmission) -> dict[str, Any]:
        terms = AcademicTerm.objects.all().order_by("-year", "period")
        return {"submission": submission, "form": DatasetResolutionForm(), "terms": terms}

    def get(self, request, submission_id: int):
        submission = self.get_submission(submission_id)
        return render(request, self.template_name, self.get_context(submission))

    def post(self, request, submission_id: int):
        submission = self.get_submission(submission_id)
        form = DatasetResolutionForm(request.POST)
        target_term_id = request.POST.get("target_term")
        if form.is_valid():
            try:
                _service.resolve_rejection(
                    submission=submission,
                    decided_by=cast(User, request.user),
                    resolution=form.cleaned_data["resolution"],
                    note=form.cleaned_data.get("note") or None,
                    target_term=AcademicTerm.objects.filter(pk=target_term_id).first() if target_term_id else None,
                )
                return redirect("audits:resolution_list")
            except Exception as exc:
                form.add_error(None, str(exc))
        context = self.get_context(submission)
        context["form"] = form
        return render(request, self.template_name, context, status=400)
