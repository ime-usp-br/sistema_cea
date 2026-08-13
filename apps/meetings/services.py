from datetime import date, datetime
from datetime import time as time_type
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from applications.models import ServiceApplication
from payments.services import (
    APPLICATION_FEE_CONSULTATION,
    CONSULTATION_TO_PROJECT_CREDIT,
    FeeCalculationService,
    record_application_event,
)

from .models import ConsultationMeeting, ProjectScreening

MEETING_MODE_ONLINE = "online"
MEETING_MODE_IN_PERSON = "in_person"


class MeetingDomainError(ValueError):
    """Erro de domínio para o módulo de agendamentos e decisões."""


def _validate_meeting_mode_fields(
    *,
    meeting_mode: str,
    virtual_link: str | None,
    place: str | None,
) -> None:
    if meeting_mode == MEETING_MODE_ONLINE:
        if not virtual_link:
            raise MeetingDomainError(
                "Reuniões online exigem um link de vídeo (virtual_link)."
            )
        if place:
            raise MeetingDomainError(
                "Reuniões online não devem informar um local presencial."
            )
    elif meeting_mode == MEETING_MODE_IN_PERSON:
        if not place:
            raise MeetingDomainError(
                "Reuniões presenciais exigem um local (place)."
            )
        if virtual_link:
            raise MeetingDomainError(
                "Reuniões presenciais não devem informar um link de vídeo."
            )
    else:
        raise MeetingDomainError(f"Modo de reunião inválido: {meeting_mode}.")


class ProjectScreeningService:
    """Serviço de domínio do fluxo de triagens de Projetos."""

    def __init__(
        self,
        *,
        fee_service: FeeCalculationService | None = None,
    ) -> None:
        self.fee_service = fee_service or FeeCalculationService()

    def schedule_screening(
        self,
        *,
        application: ServiceApplication,
        scheduled_by: Any,
        scheduled_date: date,
        scheduled_time: time_type,
        meeting_mode: str,
        virtual_link: str | None = None,
        place: str | None = None,
    ) -> ProjectScreening:
        if application.modality != ServiceApplication.Modality.PROJECT:
            raise MeetingDomainError("Triagens são exclusivas de inscrições de Projeto.")
        if (
            application.lifecycle_status
            != ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
        ):
            raise MeetingDomainError(
                "A inscrição não está aguardando o agendamento da triagem."
            )
        if ProjectScreening.objects.filter(application=application).exists():
            raise MeetingDomainError("Esta inscrição já possui uma triagem agendada.")
        _validate_meeting_mode_fields(
            meeting_mode=meeting_mode,
            virtual_link=virtual_link,
            place=place,
        )
        with transaction.atomic():
            screening = ProjectScreening.objects.create(
                application=application,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                meeting_mode=meeting_mode,
                virtual_link=virtual_link,
                place=place,
                state=ProjectScreening.State.SCHEDULED,
            )
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_SCREENING_RESULT
            )
            application.save(update_fields=["lifecycle_status", "updated_at"])
            record_application_event(
                application=application,
                event_code="meeting.screening_scheduled",
                actor=scheduled_by,
                description=f"Triagem agendada para {scheduled_date} às {scheduled_time}.",
                metadata={"screening_id": screening.pk, "mode": meeting_mode},
            )
        return screening

    def reschedule_screening(
        self,
        *,
        screening: ProjectScreening,
        rescheduled_by: Any,
        scheduled_date: date,
        scheduled_time: time_type,
        meeting_mode: str | None = None,
        virtual_link: str | None = None,
        place: str | None = None,
    ) -> ProjectScreening:
        application = screening.application
        if screening.state == ProjectScreening.State.CANCELED:
            raise MeetingDomainError("Triagens canceladas não podem ser reagendadas.")
        mode = meeting_mode or screening.meeting_mode
        link = virtual_link if virtual_link is not None else screening.virtual_link
        local = place if place is not None else screening.place
        if mode == MEETING_MODE_ONLINE:
            # Trocar para Online limpa qualquer local presencial anterior.
            local = None
        elif mode == MEETING_MODE_IN_PERSON:
            # Trocar para Presencial limpa o link online anterior.
            link = None
        _validate_meeting_mode_fields(meeting_mode=mode, virtual_link=link, place=local)
        with transaction.atomic():
            screening.scheduled_date = scheduled_date
            screening.scheduled_time = scheduled_time
            screening.meeting_mode = mode
            screening.virtual_link = link
            screening.place = local
            screening.state = ProjectScreening.State.RESCHEDULED
            screening.save(
                update_fields=[
                    "scheduled_date",
                    "scheduled_time",
                    "meeting_mode",
                    "virtual_link",
                    "place",
                    "state",
                    "updated_at",
                ]
            )
            record_application_event(
                application=application,
                event_code="meeting.screening_rescheduled",
                actor=rescheduled_by,
                description=f"Triagem reagendada para {scheduled_date} às {scheduled_time}.",
                metadata={"screening_id": screening.pk},
            )
        return screening

    def cancel_screening(
        self,
        *,
        screening: ProjectScreening,
        canceled_by: Any,
    ) -> ProjectScreening:
        application = screening.application
        if screening.state == ProjectScreening.State.CANCELED:
            raise MeetingDomainError("Esta triagem já foi cancelada.")
        with transaction.atomic():
            screening.state = ProjectScreening.State.CANCELED
            screening.save(update_fields=["state", "updated_at"])
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
            )
            application.save(update_fields=["lifecycle_status", "updated_at"])
            record_application_event(
                application=application,
                event_code="meeting.screening_canceled",
                actor=canceled_by,
                description="Triagem cancelada.",
                metadata={"screening_id": screening.pk},
            )
        return screening

    def record_decision(
        self,
        *,
        screening: ProjectScreening,
        decided_by: Any,
        decision: str,
        decision_note: str | None = None,
    ) -> ProjectScreening:
        application = screening.application
        if screening.state == ProjectScreening.State.CANCELED:
            raise MeetingDomainError(
                "Triagens canceladas não podem receber decisão."
            )
        if (
            application.lifecycle_status
            != ServiceApplication.LifecycleStatus.AWAITING_SCREENING_RESULT
        ):
            raise MeetingDomainError(
                "A inscrição não está aguardando o resultado da triagem."
            )
        decision_enum = ProjectScreening.Decision(decision)
        with transaction.atomic():
            screening.decision = decision_enum.value
            screening.decision_note = decision_note
            screening.state = ProjectScreening.State.COMPLETED
            screening.save(
                update_fields=["decision", "decision_note", "state", "updated_at"]
            )
            self._apply_screening_decision(application, decision_enum, decided_by)
            record_application_event(
                application=application,
                event_code="meeting.screening_decided",
                actor=decided_by,
                description=f"Decisão da triagem: {decision_enum.value}.",
                metadata={
                    "screening_id": screening.pk,
                    "decision": decision_enum.value,
                },
            )
        return screening

    def record_feedback(
        self,
        *,
        screening: ProjectScreening,
        recorded_by: Any,
        teacher_feedback: str,
    ) -> ProjectScreening:
        if screening.state == ProjectScreening.State.CANCELED:
            raise MeetingDomainError(
                "Triagens canceladas não podem receber feedback."
            )
        now = timezone.now()
        scheduled_dt = _combine_aware(screening.scheduled_date, screening.scheduled_time)
        if now <= scheduled_dt:
            raise MeetingDomainError(
                "O feedback do docente só pode ser registrado após a data e hora do evento."
            )
        feedback_enum = ProjectScreening.TeacherFeedback(teacher_feedback)
        with transaction.atomic():
            screening.teacher_feedback = feedback_enum.value
            screening.save(update_fields=["teacher_feedback", "updated_at"])
            record_application_event(
                application=screening.application,
                event_code="meeting.screening_feedback_recorded",
                actor=recorded_by,
                description=f"Feedback da triagem: {feedback_enum.value}.",
                metadata={"screening_id": screening.pk},
            )
        return screening

    def _apply_screening_decision(
        self,
        application: ServiceApplication,
        decision: ProjectScreening.Decision,
        decided_by: Any,
    ) -> None:
        if decision == ProjectScreening.Decision.APPROVED_AS_PROJECT:
            self.fee_service.create_project_fee(application)
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT
            )
            application.save(update_fields=["lifecycle_status", "updated_at"])
        elif decision == ProjectScreening.Decision.APPROVED_AS_CONSULTATION:
            self._apply_approved_as_consultation(application, decided_by)
        elif decision == ProjectScreening.Decision.NOT_APPROVED:
            application.lifecycle_status = ServiceApplication.LifecycleStatus.NOT_APPROVED
            application.save(update_fields=["lifecycle_status", "updated_at"])

    def _apply_approved_as_consultation(
        self,
        application: ServiceApplication,
        decided_by: Any,
    ) -> None:
        """Converte o Projeto em Consulta criando o complemento se necessário (TS-MEET-010)."""
        app_fee = application.fee_requirements.filter(
            fee_type="application_fee"
        ).first()
        if app_fee is not None and app_fee.is_paid:
            if app_fee.paid_amount < APPLICATION_FEE_CONSULTATION:
                self.fee_service.create_supplement_fee(
                    application,
                    amount=APPLICATION_FEE_CONSULTATION - app_fee.paid_amount,
                )
        elif app_fee is not None:
            app_fee.base_amount = APPLICATION_FEE_CONSULTATION
            app_fee.adjustment_amount = Decimal("0.00")
            app_fee.amount = APPLICATION_FEE_CONSULTATION
            app_fee.save(
                update_fields=["base_amount", "adjustment_amount", "amount", "updated_at"]
            )
        else:
            self.fee_service.create_application_fee(application)
        application.modality = ServiceApplication.Modality.CONSULTATION
        application.dataset_audit_required = False
        application.dataset_audit_state = None
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.APPROVED_AS_CONSULTATION
        )
        application.save(
            update_fields=[
                "modality",
                "dataset_audit_required",
                "dataset_audit_state",
                "lifecycle_status",
                "updated_at",
            ]
        )


class ConsultationMeetingService:
    """Serviço de domínio do fluxo de reuniões de Consulta."""

    def __init__(
        self,
        *,
        fee_service: FeeCalculationService | None = None,
    ) -> None:
        self.fee_service = fee_service or FeeCalculationService()

    def schedule_consultation(
        self,
        *,
        application: ServiceApplication,
        scheduled_by: Any,
        scheduled_date: date,
        scheduled_time: time_type,
        meeting_mode: str,
        virtual_link: str | None = None,
        place: str | None = None,
    ) -> ConsultationMeeting:
        if application.modality != ServiceApplication.Modality.CONSULTATION:
            raise MeetingDomainError(
                "Reuniões são exclusivas de inscrições de Consulta."
            )
        if (
            application.lifecycle_status
            != ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
        ):
            raise MeetingDomainError(
                "A inscrição não está aguardando o agendamento da reunião."
            )
        if ConsultationMeeting.objects.filter(application=application).exists():
            raise MeetingDomainError(
                "Esta inscrição já possui uma reunião agendada."
            )
        _validate_meeting_mode_fields(
            meeting_mode=meeting_mode,
            virtual_link=virtual_link,
            place=place,
        )
        with transaction.atomic():
            meeting = ConsultationMeeting.objects.create(
                application=application,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                meeting_mode=meeting_mode,
                virtual_link=virtual_link,
                place=place,
                state=ConsultationMeeting.State.SCHEDULED,
            )
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_RESULT
            )
            application.save(update_fields=["lifecycle_status", "updated_at"])
            record_application_event(
                application=application,
                event_code="meeting.consultation_scheduled",
                actor=scheduled_by,
                description=f"Reunião agendada para {scheduled_date} às {scheduled_time}.",
                metadata={"meeting_id": meeting.pk, "mode": meeting_mode},
            )
        return meeting

    def reschedule_consultation(
        self,
        *,
        meeting: ConsultationMeeting,
        rescheduled_by: Any,
        scheduled_date: date,
        scheduled_time: time_type,
        meeting_mode: str | None = None,
        virtual_link: str | None = None,
        place: str | None = None,
    ) -> ConsultationMeeting:
        application = meeting.application
        if meeting.state == ConsultationMeeting.State.CANCELED:
            raise MeetingDomainError("Reuniões canceladas não podem ser reagendadas.")
        mode = meeting_mode or meeting.meeting_mode
        link = virtual_link if virtual_link is not None else meeting.virtual_link
        local = place if place is not None else meeting.place
        if mode == MEETING_MODE_ONLINE:
            local = None
        elif mode == MEETING_MODE_IN_PERSON:
            link = None
        _validate_meeting_mode_fields(meeting_mode=mode, virtual_link=link, place=local)
        with transaction.atomic():
            meeting.scheduled_date = scheduled_date
            meeting.scheduled_time = scheduled_time
            meeting.meeting_mode = mode
            meeting.virtual_link = link
            meeting.place = local
            meeting.state = ConsultationMeeting.State.RESCHEDULED
            meeting.save(
                update_fields=[
                    "scheduled_date",
                    "scheduled_time",
                    "meeting_mode",
                    "virtual_link",
                    "place",
                    "state",
                    "updated_at",
                ]
            )
            record_application_event(
                application=application,
                event_code="meeting.consultation_rescheduled",
                actor=rescheduled_by,
                description=f"Reunião reagendada para {scheduled_date} às {scheduled_time}.",
                metadata={"meeting_id": meeting.pk},
            )
        return meeting

    def cancel_consultation(
        self,
        *,
        meeting: ConsultationMeeting,
        canceled_by: Any,
    ) -> ConsultationMeeting:
        application = meeting.application
        if meeting.state == ConsultationMeeting.State.CANCELED:
            raise MeetingDomainError("Esta reunião já foi cancelada.")
        with transaction.atomic():
            meeting.state = ConsultationMeeting.State.CANCELED
            meeting.save(update_fields=["state", "updated_at"])
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
            )
            application.save(update_fields=["lifecycle_status", "updated_at"])
            record_application_event(
                application=application,
                event_code="meeting.consultation_canceled",
                actor=canceled_by,
                description="Reunião cancelada.",
                metadata={"meeting_id": meeting.pk},
            )
        return meeting

    def record_decision(
        self,
        *,
        meeting: ConsultationMeeting,
        decided_by: Any,
        decision: str,
        decision_note: str | None = None,
    ) -> ConsultationMeeting:
        application = meeting.application
        if (
            application.lifecycle_status
            != ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_RESULT
        ):
            raise MeetingDomainError(
                "A inscrição não está aguardando o resultado da reunião."
            )
        decision_enum = ConsultationMeeting.Decision(decision)
        with transaction.atomic():
            meeting.decision = decision_enum.value
            meeting.decision_note = decision_note
            meeting.state = ConsultationMeeting.State.COMPLETED
            meeting.save(
                update_fields=["decision", "decision_note", "state", "updated_at"]
            )
            self._apply_meeting_decision(application, decision_enum)
            record_application_event(
                application=application,
                event_code="meeting.consultation_decided",
                actor=decided_by,
                description=f"Decisão da reunião: {decision_enum.value}.",
                metadata={"meeting_id": meeting.pk, "decision": decision_enum.value},
            )
        return meeting

    def record_feedback(
        self,
        *,
        meeting: ConsultationMeeting,
        recorded_by: Any,
        teacher_feedback: str,
    ) -> ConsultationMeeting:
        now = timezone.now()
        scheduled_dt = _combine_aware(meeting.scheduled_date, meeting.scheduled_time)
        if now <= scheduled_dt:
            raise MeetingDomainError(
                "O feedback do docente só pode ser registrado após a data e hora do evento."
            )
        feedback_enum = ConsultationMeeting.TeacherFeedback(teacher_feedback)
        with transaction.atomic():
            meeting.teacher_feedback = feedback_enum.value
            meeting.save(update_fields=["teacher_feedback", "updated_at"])
            record_application_event(
                application=meeting.application,
                event_code="meeting.consultation_feedback_recorded",
                actor=recorded_by,
                description=f"Feedback da reunião: {feedback_enum.value}.",
                metadata={"meeting_id": meeting.pk},
            )
        return meeting

    def _apply_meeting_decision(
        self,
        application: ServiceApplication,
        decision: ConsultationMeeting.Decision,
    ) -> None:
        if decision == ConsultationMeeting.Decision.APPROVED_AS_PROJECT:
            self._apply_approved_as_project(application)
        elif decision == ConsultationMeeting.Decision.APPROVED_AS_CONSULTATION:
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.APPROVED_AS_CONSULTATION
            )
            application.save(update_fields=["lifecycle_status", "updated_at"])
        elif decision == ConsultationMeeting.Decision.NOT_APPROVED:
            application.lifecycle_status = ServiceApplication.LifecycleStatus.NOT_APPROVED
            application.save(update_fields=["lifecycle_status", "updated_at"])

    def _apply_approved_as_project(
        self,
        application: ServiceApplication,
    ) -> None:
        """Redireciona uma Consulta para o fluxo de Projeto (TS-MEET-014).

        Paridade com o ``ConsultationMeetingController`` do legado: quando o
        docente decide ``approved_as_project``, a inscrição passa a Projeto e o
        sistema gera a Taxa de Projeto (R$ 250,00).
        """
        application.modality = ServiceApplication.Modality.PROJECT
        app_fee = application.fee_requirements.filter(
            fee_type="application_fee"
        ).first()
        if app_fee is not None and app_fee.is_paid:
            application.modality_credit_amount = CONSULTATION_TO_PROJECT_CREDIT
        self.fee_service.create_project_fee(application)
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT
        )
        application.save(
            update_fields=[
                "modality",
                "modality_credit_amount",
                "lifecycle_status",
                "updated_at",
            ]
        )


def _combine_aware(scheduled_date: date, scheduled_time: time_type) -> datetime:
    """Combina data e hora agendadas em um datetime timezone-aware."""
    naive = datetime.combine(scheduled_date, scheduled_time)
    if timezone.is_aware(naive):
        return naive
    return timezone.make_aware(naive)
