from typing import Any, cast

from django.contrib import messages
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
# O feedback do docente é registrado pelo docente; a decisão final é da
# secretaria (perfis distintos, conforme ARCHITECTURE.md §7.3/§7.4).
_FEEDBACK_ROLES = frozenset({User.Role.TEACHER, User.Role.ADMINISTRATOR})


def _can(user: User, roles: frozenset[str]) -> bool:
    return user.is_superuser or user.role in roles


def _ordered_choices(choices, first_value: str) -> list[tuple[str, str]]:
    """Reordena choices colocando ``first_value`` como primeira opção.

    Evita induzir a secretaria ao erro ao registrar a decisão: a opção de
    aprovação na própria modalidade sempre aparece em primeiro lugar.
    """
    items = list(choices)
    items.sort(key=lambda item: item[0] != first_value)
    return items


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
    """Fila de agendamentos: pendentes de agendamento e aguardando resultado."""

    allowed_roles = _STAFF_ROLES
    template_name = "meetings/scheduling_queue.html"

    def get(self, request):
        user = cast(User, request.user)
        # A secretaria vê a fila completa (agendar + registrar decisão); o
        # docente vê apenas os itens "aguardando resultado", onde registra o
        # feedback.
        show_management = _can(user, _SECRETARIAT_ROLES)
        projects = (
            ServiceApplication.objects.select_related("term", "owner", "project_screening")
            .filter(
                lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
            )
            .order_by("-created_at")
        )
        consultations = (
            ServiceApplication.objects.select_related("term", "owner", "consultation_meeting")
            .filter(
                lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
            )
            .order_by("-created_at")
        )
        screenings_result = (
            ServiceApplication.objects.select_related("term", "owner", "project_screening")
            .filter(
                lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_SCREENING_RESULT
            )
            .order_by("-project_screening__scheduled_date",
                      "-project_screening__scheduled_time")
        )
        consultations_result = (
            ServiceApplication.objects.select_related("term", "owner", "consultation_meeting")
            .filter(
                lifecycle_status=ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_RESULT
            )
            .order_by("-consultation_meeting__scheduled_date",
                      "-consultation_meeting__scheduled_time")
        )
        return render(
            request,
            self.template_name,
            {
                "projects": projects if show_management else [],
                "consultations": consultations if show_management else [],
                "screenings_result": screenings_result,
                "consultations_result": consultations_result,
                "can_register_feedback": _can(user, _FEEDBACK_ROLES),
                "can_register_decision": _can(user, _SECRETARIAT_ROLES),
            },
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
    """Registro de feedback (docente) e decisão (secretaria) da triagem.

    Operações separadas por perfil: o docente registra o feedback da
    triagem; a secretaria (ou admin) registra a decisão final.
    """

    allowed_roles = _STAFF_ROLES
    template_name = "meetings/screening_decision.html"

    def get_screening(self, screening_id: int) -> ProjectScreening:
        return get_object_or_404(
            ProjectScreening.objects.select_related("application"),
            pk=screening_id,
        )

    def get_context(self, request, screening: ProjectScreening, **kwargs) -> dict[str, Any]:
        user = cast(User, request.user)
        context = {
            "screening": screening,
            "can_register_feedback": _can(user, _FEEDBACK_ROLES),
            "can_register_decision": _can(user, _SECRETARIAT_ROLES),
            "decision_form": MeetingDecisionForm(
                decision_choices=_ordered_choices(
                    ProjectScreening.Decision.choices,
                    ProjectScreening.Decision.APPROVED_AS_PROJECT.value,
                )
            ),
            "feedback_form": TeacherFeedbackForm(
                teacher_feedback_choices=ProjectScreening.TeacherFeedback.choices
            ),
        }
        context.update(kwargs)
        return context

    def get(self, request, screening_id: int):
        screening = self.get_screening(screening_id)
        return render(
            request, self.template_name, self.get_context(request, screening)
        )

    def post(self, request, screening_id: int):
        screening = self.get_screening(screening_id)
        if (
            "submit_feedback" in request.POST
            or request.POST.get("form_action") == "feedback"
        ):
            return self._handle_feedback(request, screening)
        return self._handle_decision(request, screening)

    def _handle_decision(self, request, screening: ProjectScreening):
        user = cast(User, request.user)
        if not _can(user, _SECRETARIAT_ROLES):
            raise PermissionDenied(
                "Somente a secretaria pode registrar a decisão da triagem."
            )
        form = MeetingDecisionForm(
            request.POST,
            decision_choices=_ordered_choices(
                ProjectScreening.Decision.choices,
                ProjectScreening.Decision.APPROVED_AS_PROJECT.value,
            ),
        )
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(request, screening, decision_form=form),
                status=400,
            )
        try:
            _screening_service.record_decision(
                screening=screening,
                decided_by=user,
                decision=form.cleaned_data["decision"],
                decision_note=form.cleaned_data.get("decision_note") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(request, screening, decision_form=form),
                status=400,
            )
        messages.success(
            request,
            f"Decisão da triagem registrada: "
            f"{ProjectScreening.Decision(form.cleaned_data['decision']).label}.",
        )
        return redirect("meetings:queue")

    def _handle_feedback(self, request, screening: ProjectScreening):
        user = cast(User, request.user)
        if not _can(user, _FEEDBACK_ROLES):
            raise PermissionDenied(
                "Somente o docente pode registrar o feedback da triagem."
            )
        form = TeacherFeedbackForm(
            request.POST,
            teacher_feedback_choices=ProjectScreening.TeacherFeedback.choices,
        )
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(request, screening, feedback_form=form),
                status=400,
            )
        try:
            _screening_service.record_feedback(
                screening=screening,
                recorded_by=user,
                teacher_feedback=form.cleaned_data["teacher_feedback"],
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(request, screening, feedback_form=form),
                status=400,
            )
        messages.success(
            request,
            "Feedback do docente registrado: "
            f"{ProjectScreening.TeacherFeedback(form.cleaned_data['teacher_feedback']).label}.",
        )
        return redirect("meetings:queue")


class ConsultationDecisionView(RoleRequiredMixin, View):
    """Registro de feedback (docente) e decisão (secretaria) da reunião.

    Operações separadas por perfil: o docente registra o feedback da
    reunião; a secretaria (ou admin) registra a decisão final.
    """

    allowed_roles = _STAFF_ROLES
    template_name = "meetings/consultation_decision.html"

    def get_meeting(self, meeting_id: int) -> ConsultationMeeting:
        return get_object_or_404(
            ConsultationMeeting.objects.select_related("application"),
            pk=meeting_id,
        )

    def get_context(self, request, meeting: ConsultationMeeting, **kwargs) -> dict[str, Any]:
        user = cast(User, request.user)
        context = {
            "meeting": meeting,
            "can_register_feedback": _can(user, _FEEDBACK_ROLES),
            "can_register_decision": _can(user, _SECRETARIAT_ROLES),
            "decision_form": MeetingDecisionForm(
                decision_choices=_ordered_choices(
                    ConsultationMeeting.Decision.choices,
                    ConsultationMeeting.Decision.APPROVED_AS_CONSULTATION.value,
                )
            ),
            "feedback_form": TeacherFeedbackForm(
                teacher_feedback_choices=ConsultationMeeting.TeacherFeedback.choices
            ),
        }
        context.update(kwargs)
        return context

    def get(self, request, meeting_id: int):
        meeting = self.get_meeting(meeting_id)
        return render(request, self.template_name, self.get_context(request, meeting))

    def post(self, request, meeting_id: int):
        meeting = self.get_meeting(meeting_id)
        if (
            "submit_feedback" in request.POST
            or request.POST.get("form_action") == "feedback"
        ):
            return self._handle_feedback(request, meeting)
        return self._handle_decision(request, meeting)

    def _handle_decision(self, request, meeting: ConsultationMeeting):
        user = cast(User, request.user)
        if not _can(user, _SECRETARIAT_ROLES):
            raise PermissionDenied(
                "Somente a secretaria pode registrar a decisão da reunião."
            )
        form = MeetingDecisionForm(
            request.POST,
            decision_choices=_ordered_choices(
                ConsultationMeeting.Decision.choices,
                ConsultationMeeting.Decision.APPROVED_AS_CONSULTATION.value,
            ),
        )
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(request, meeting, decision_form=form),
                status=400,
            )
        try:
            _consultation_service.record_decision(
                meeting=meeting,
                decided_by=user,
                decision=form.cleaned_data["decision"],
                decision_note=form.cleaned_data.get("decision_note") or None,
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(request, meeting, decision_form=form),
                status=400,
            )
        messages.success(
            request,
            f"Decisão da reunião registrada: "
            f"{ConsultationMeeting.Decision(form.cleaned_data['decision']).label}.",
        )
        return redirect("meetings:queue")

    def _handle_feedback(self, request, meeting: ConsultationMeeting):
        user = cast(User, request.user)
        if not _can(user, _FEEDBACK_ROLES):
            raise PermissionDenied(
                "Somente o docente pode registrar o feedback da reunião."
            )
        form = TeacherFeedbackForm(
            request.POST,
            teacher_feedback_choices=ConsultationMeeting.TeacherFeedback.choices,
        )
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.get_context(request, meeting, feedback_form=form),
                status=400,
            )
        try:
            _consultation_service.record_feedback(
                meeting=meeting,
                recorded_by=user,
                teacher_feedback=form.cleaned_data["teacher_feedback"],
            )
        except Exception as exc:
            form.add_error(None, str(exc))
            return render(
                request,
                self.template_name,
                self.get_context(request, meeting, feedback_form=form),
                status=400,
            )
        messages.success(
            request,
            "Feedback do docente registrado: "
            f"{ConsultationMeeting.TeacherFeedback(form.cleaned_data['teacher_feedback']).label}.",
        )
        return redirect("meetings:queue")
