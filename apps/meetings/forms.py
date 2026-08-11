from typing import Any

from django import forms

from .models import ConsultationMeeting, ProjectScreening


class ScreeningForm(forms.Form):
    """Formulário de agendamento de triagem pela secretaria."""

    scheduled_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Data agendada",
    )
    scheduled_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Hora agendada",
    )
    meeting_mode = forms.ChoiceField(
        choices=ProjectScreening.MeetingMode.choices,
        label="Modalidade",
    )
    virtual_link = forms.URLField(
        required=False,
        max_length=2048,
        assume_scheme="https",
        label="Link de vídeo (online)",
    )
    place = forms.CharField(required=False, max_length=255, label="Local (presencial)")

    def clean(self):
        cleaned_data = super().clean() or {}
        mode = cleaned_data.get("meeting_mode")
        virtual_link = cleaned_data.get("virtual_link")
        place = cleaned_data.get("place")
        if mode == ProjectScreening.MeetingMode.ONLINE.value and not virtual_link:
            self.add_error("virtual_link", "Reuniões online exigem um link de vídeo.")
        elif mode == ProjectScreening.MeetingMode.IN_PERSON.value and not place:
            self.add_error("place", "Reuniões presenciais exigem um local.")
        return cleaned_data


class ConsultationMeetingForm(ScreeningForm):
    """Formulário de agendamento de reunião de consulta."""

    meeting_mode = forms.ChoiceField(
        choices=ConsultationMeeting.MeetingMode.choices,
        label="Modalidade",
    )


class MeetingDecisionForm(forms.Form):
    """Formulário de decisão final registrada pelo docente/secretaria."""

    decision = forms.ChoiceField(label="Decisão final")
    decision_note = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Observação",
    )

    def __init__(self, *args, decision_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if decision_choices is not None:
            field: Any = self.fields["decision"]
            field.choices = decision_choices


class TeacherFeedbackForm(forms.Form):
    """Formulário de feedback do docente após o evento."""

    teacher_feedback = forms.ChoiceField(label="Feedback do docente")
