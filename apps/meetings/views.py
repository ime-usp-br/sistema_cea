from typing import Any, cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from applications.models import ServiceApplication
from users.models import User

from .forms import (
    ConsultationMeetingForm,
    MeetingDecisionForm,
    ScreeningForm,
    TeacherFeedbackForm,
)
from .models import ConsultationMeeting, ProjectScreening
from .services import (
    ConsultationMeetingService,
    ProjectScreeningService,
)

_screening_service = ProjectScreeningService()
_consultation_service = ConsultationMeetingService()

_STAFF_ROLES = frozenset(
    {User.Role.TEACHER, User.Role.SECRETARIAT, User.Role.ADMINISTRATOR}
)
_SECRETARIAT_ROLES = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})


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


class SchedulingQueueView(RoleRequiredMixin, View):
    """Fila de agendamentos pendentes (Projetos e Consultas pagos)."""

    allowed_roles = _STAFF_ROLES
    template_name = "meetings/scheduling_queue.html"

    def get(self, request):
        projects = (
            ServiceApplication.objects.select_related("term", "owner")
            .filter(
                lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
            )
            .order_by("-created_at")
        )
        consultations = (
            ServiceApplication.objects.select_related("term", "owner")
            .filter(
                lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
            )
            .order_by("-created_at")
        )
        return render(
            request,
            self.template_name,
            {"projects": projects, "consultations": consultations},
        )


class ScreeningScheduleView(RoleRequiredMixin, View):
    """Secretaria agenda, reagenda ou cancela uma triagem."""

    allowed_roles = _SECRETARIAT_ROLES
    template_name = "meetings/screening_form.html"

    def get_application(self, protocol: str) -> ServiceApplication:
        return get_object_or_404(ServiceApplication, protocol=protocol)

    def get_context(self, application: ServiceApplication, form=None) -> dict[str, Any]:
        screening = getattr(application, "project_screening", None)
        return {
            "application": application,
            "screening": screening,
            "form": form or ScreeningForm(),
        }

    def get(self, request, protocol: str):
        application = self.get_application(protocol)
        return render(request, self.template_name, self.get_context(application))

    def post(self, request, protocol: str):
        application = self.get_application(protocol)
        action = request.POST.get("action")
        screening = getattr(application, "project_screening", None)
        if action == "cancel":
            if screening is None:
                raise PermissionDenied("Não há triagem para cancelar.")
            _screening_service.cancel_screening(
                screening=screening,
                canceled_by=cast(User, request.user),
            )
            return redirect("meetings:queue")
        form = ScreeningForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(application, form),
                status=400,
            )
        data = form.cleaned_data
        try:
            if screening is None:
                _screening_service.schedule_screening(
                    application=application,
                    scheduled_by=cast(User, request.user),
                    scheduled_date=data["scheduled_date"],
                    scheduled_time=data["scheduled_time"],
                    meeting_mode=data["meeting_mode"],
                    virtual_link=data.get("virtual_link") or None,
                    place=data.get("place") or None,
                )
            else:
                _screening_service.reschedule_screening(
                    screening=screening,
                    rescheduled_by=cast(User, request.user),
                    scheduled_date=data["scheduled_date"],
                    scheduled_time=data["scheduled_time"],
                    meeting_mode=data["meeting_mode"],
                    virtual_link=data.get("virtual_link") or None,
                    place=data.get("place") or None,
                )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(application, form),
                status=400,
            )
        return redirect("meetings:queue")


class ConsultationScheduleView(RoleRequiredMixin, View):
    """Secretaria agenda, reagenda ou cancela uma reunião de consulta."""

    allowed_roles = _SECRETARIAT_ROLES
    template_name = "meetings/consultation_form.html"

    def get_application(self, protocol: str) -> ServiceApplication:
        return get_object_or_404(ServiceApplication, protocol=protocol)

    def get_context(self, application: ServiceApplication, form=None) -> dict[str, Any]:
        meeting = getattr(application, "consultation_meeting", None)
        return {
            "application": application,
            "meeting": meeting,
            "form": form or ConsultationMeetingForm(),
        }

    def get(self, request, protocol: str):
        application = self.get_application(protocol)
        return render(request, self.template_name, self.get_context(application))

    def post(self, request, protocol: str):
        application = self.get_application(protocol)
        action = request.POST.get("action")
        meeting = getattr(application, "consultation_meeting", None)
        if action == "cancel":
            if meeting is None:
                raise PermissionDenied("Não há reunião para cancelar.")
            _consultation_service.cancel_consultation(
                meeting=meeting,
                canceled_by=cast(User, request.user),
            )
            return redirect("meetings:queue")
        form = ConsultationMeetingForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(application, form),
                status=400,
            )
        data = form.cleaned_data
        try:
            if meeting is None:
                _consultation_service.schedule_consultation(
                    application=application,
                    scheduled_by=cast(User, request.user),
                    scheduled_date=data["scheduled_date"],
                    scheduled_time=data["scheduled_time"],
                    meeting_mode=data["meeting_mode"],
                    virtual_link=data.get("virtual_link") or None,
                    place=data.get("place") or None,
                )
            else:
                _consultation_service.reschedule_consultation(
                    meeting=meeting,
                    rescheduled_by=cast(User, request.user),
                    scheduled_date=data["scheduled_date"],
                    scheduled_time=data["scheduled_time"],
                    meeting_mode=data["meeting_mode"],
                    virtual_link=data.get("virtual_link") or None,
                    place=data.get("place") or None,
                )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(application, form),
                status=400,
            )
        return redirect("meetings:queue")


class ScreeningDecisionView(RoleRequiredMixin, View):
    """Docente/secretaria registra decisão e feedback da triagem."""

    allowed_roles = _STAFF_ROLES
    template_name = "meetings/screening_decision.html"

    def get_screening(self, screening_id: int) -> ProjectScreening:
        return get_object_or_404(
            ProjectScreening.objects.select_related("application"),
            pk=screening_id,
        )

    def get_context(self, screening: ProjectScreening, **kwargs) -> dict[str, Any]:
        context = {
            "screening": screening,
            "decision_form": MeetingDecisionForm(
                decision_choices=ProjectScreening.Decision.choices
            ),
            "feedback_form": TeacherFeedbackForm(),
        }
        context.update(kwargs)
        return context

    def get(self, request, screening_id: int):
        screening = self.get_screening(screening_id)
        return render(request, self.template_name, self.get_context(screening))

    def post(self, request, screening_id: int):
        screening = self.get_screening(screening_id)
        if request.POST.get("submit_feedback"):
            return self._handle_feedback(request, screening)
        return self._handle_decision(request, screening)

    def _handle_decision(self, request, screening: ProjectScreening):
        form = MeetingDecisionForm(
            request.POST,
            decision_choices=ProjectScreening.Decision.choices,
        )
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(screening, decision_form=form),
                status=400,
            )
        try:
            _screening_service.record_decision(
                screening=screening,
                decided_by=cast(User, request.user),
                decision=form.cleaned_data["decision"],
                decision_note=form.cleaned_data.get("decision_note") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(screening, decision_form=form),
                status=400,
            )
        return redirect("meetings:queue")

    def _handle_feedback(self, request, screening: ProjectScreening):
        form = TeacherFeedbackForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(screening, feedback_form=form),
                status=400,
            )
        try:
            _screening_service.record_feedback(
                screening=screening,
                recorded_by=cast(User, request.user),
                teacher_feedback=form.cleaned_data["teacher_feedback"],
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(screening, feedback_form=form),
                status=400,
            )
        return redirect("meetings:queue")


class ConsultationDecisionView(RoleRequiredMixin, View):
    """Docente/secretaria registra decisão e feedback da reunião."""

    allowed_roles = _STAFF_ROLES
    template_name = "meetings/consultation_decision.html"

    def get_meeting(self, meeting_id: int) -> ConsultationMeeting:
        return get_object_or_404(
            ConsultationMeeting.objects.select_related("application"),
            pk=meeting_id,
        )

    def get_context(self, meeting: ConsultationMeeting, **kwargs) -> dict[str, Any]:
        context = {
            "meeting": meeting,
            "decision_form": MeetingDecisionForm(
                decision_choices=ConsultationMeeting.Decision.choices
            ),
            "feedback_form": TeacherFeedbackForm(),
        }
        context.update(kwargs)
        return context

    def get(self, request, meeting_id: int):
        meeting = self.get_meeting(meeting_id)
        return render(request, self.template_name, self.get_context(meeting))

    def post(self, request, meeting_id: int):
        meeting = self.get_meeting(meeting_id)
        if request.POST.get("submit_feedback"):
            return self._handle_feedback(request, meeting)
        return self._handle_decision(request, meeting)

    def _handle_decision(self, request, meeting: ConsultationMeeting):
        form = MeetingDecisionForm(
            request.POST,
            decision_choices=ConsultationMeeting.Decision.choices,
        )
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(meeting, decision_form=form),
                status=400,
            )
        try:
            _consultation_service.record_decision(
                meeting=meeting,
                decided_by=cast(User, request.user),
                decision=form.cleaned_data["decision"],
                decision_note=form.cleaned_data.get("decision_note") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(meeting, decision_form=form),
                status=400,
            )
        return redirect("meetings:queue")

    def _handle_feedback(self, request, meeting: ConsultationMeeting):
        form = TeacherFeedbackForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(meeting, feedback_form=form),
                status=400,
            )
        try:
            _consultation_service.record_feedback(
                meeting=meeting,
                recorded_by=cast(User, request.user),
                teacher_feedback=form.cleaned_data["teacher_feedback"],
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(meeting, feedback_form=form),
                status=400,
            )
        return redirect("meetings:queue")
