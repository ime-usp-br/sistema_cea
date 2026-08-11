from django.db import models


class _MeetingMode:
    ONLINE = "online"
    IN_PERSON = "in_person"


class _MeetingState:
    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    CANCELED = "canceled"
    COMPLETED = "completed"


class ProjectScreening(models.Model):
    """Triagem agendada para uma inscrição de Projeto."""

    class MeetingMode(models.TextChoices):
        ONLINE = _MeetingMode.ONLINE, "Online"
        IN_PERSON = _MeetingMode.IN_PERSON, "Presencial"

    class Decision(models.TextChoices):
        APPROVED_AS_PROJECT = "approved_as_project", "Aprovado como projeto"
        APPROVED_AS_CONSULTATION = "approved_as_consultation", "Aprovado como consulta"
        NOT_APPROVED = "not_approved", "Não aprovado"

    class TeacherFeedback(models.TextChoices):
        SCREENING_COMPLETED = "screening_completed", "Triagem realizada"
        SCREENING_NOT_COMPLETED = "screening_not_completed", "Triagem não realizada"

    class State(models.TextChoices):
        SCHEDULED = _MeetingState.SCHEDULED, "Agendada"
        RESCHEDULED = _MeetingState.RESCHEDULED, "Reagendada"
        CANCELED = _MeetingState.CANCELED, "Cancelada"
        COMPLETED = _MeetingState.COMPLETED, "Concluída"

    application = models.OneToOneField(
        "applications.ServiceApplication",
        on_delete=models.RESTRICT,
        related_name="project_screening",
    )
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    meeting_mode = models.CharField(max_length=20, choices=MeetingMode.choices)
    virtual_link = models.CharField(max_length=2048, null=True, blank=True)
    place = models.CharField(max_length=255, null=True, blank=True)
    decision = models.CharField(max_length=40, choices=Decision.choices, null=True, blank=True)
    decision_note = models.TextField(null=True, blank=True)
    teacher_feedback = models.CharField(
        max_length=50,
        choices=TeacherFeedback.choices,
        null=True,
        blank=True,
    )
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_screenings"
        ordering = ["scheduled_date", "scheduled_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(meeting_mode__in=["online", "in_person"]),
                name="chk_project_screenings_meeting_mode",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    decision__in=[
                        "approved_as_project",
                        "approved_as_consultation",
                        "not_approved",
                    ]
                ),
                name="chk_project_screenings_decision",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    teacher_feedback__in=[
                        "screening_completed",
                        "screening_not_completed",
                    ]
                ),
                name="chk_project_screenings_feedback",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=["scheduled", "rescheduled", "canceled", "completed"]),
                name="chk_project_screenings_state",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(meeting_mode="online", virtual_link__isnull=False)
                    | models.Q(meeting_mode="in_person", place__isnull=False)
                ),
                name="chk_project_screenings_mode_location",
            ),
        ]

    def __str__(self) -> str:
        return f"Triagem #{self.pk} — {self.application_id}"


class ConsultationMeeting(models.Model):
    """Reunião de consulta agendada para uma inscrição de Consulta."""

    class MeetingMode(models.TextChoices):
        ONLINE = _MeetingMode.ONLINE, "Online"
        IN_PERSON = _MeetingMode.IN_PERSON, "Presencial"

    class Decision(models.TextChoices):
        APPROVED_AS_CONSULTATION = "approved_as_consultation", "Aprovado como consulta"
        NOT_APPROVED = "not_approved", "Não aprovado"

    class TeacherFeedback(models.TextChoices):
        CONSULTATION_COMPLETED = "consultation_completed", "Reunião realizada"
        CONSULTATION_NOT_COMPLETED = "consultation_not_completed", "Reunião não realizada"

    class State(models.TextChoices):
        SCHEDULED = _MeetingState.SCHEDULED, "Agendada"
        RESCHEDULED = _MeetingState.RESCHEDULED, "Reagendada"
        CANCELED = _MeetingState.CANCELED, "Cancelada"
        COMPLETED = _MeetingState.COMPLETED, "Concluída"

    application = models.OneToOneField(
        "applications.ServiceApplication",
        on_delete=models.RESTRICT,
        related_name="consultation_meeting",
    )
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    meeting_mode = models.CharField(max_length=20, choices=MeetingMode.choices)
    virtual_link = models.CharField(max_length=2048, null=True, blank=True)
    place = models.CharField(max_length=255, null=True, blank=True)
    decision = models.CharField(max_length=40, choices=Decision.choices, null=True, blank=True)
    decision_note = models.TextField(null=True, blank=True)
    teacher_feedback = models.CharField(
        max_length=50,
        choices=TeacherFeedback.choices,
        null=True,
        blank=True,
    )
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "consultation_meetings"
        ordering = ["scheduled_date", "scheduled_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(meeting_mode__in=["online", "in_person"]),
                name="chk_consultation_meetings_meeting_mode",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    decision__in=["approved_as_consultation", "not_approved"]
                ),
                name="chk_consultation_meetings_decision",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    teacher_feedback__in=[
                        "consultation_completed",
                        "consultation_not_completed",
                    ]
                ),
                name="chk_consultation_meetings_feedback",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=["scheduled", "rescheduled", "canceled", "completed"]),
                name="chk_consultation_meetings_state",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(meeting_mode="online", virtual_link__isnull=False)
                    | models.Q(meeting_mode="in_person", place__isnull=False)
                ),
                name="chk_consultation_meetings_mode_location",
            ),
        ]

    def __str__(self) -> str:
        return f"Reunião #{self.pk} — {self.application_id}"
