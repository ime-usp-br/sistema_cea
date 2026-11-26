from __future__ import annotations

from django import forms

from .models import AcademicTerm


class AcademicTermForm(forms.ModelForm):
    """Formulário de cadastro/edição de semestre usado pela Secretaria."""

    class Meta:
        model = AcademicTerm
        fields = [
            "year",
            "period",
            "teaching_start_date",
            "teaching_end_date",
            "submission_start_date",
            "submission_end_date",
        ]
        widgets = {
            "teaching_start_date": forms.DateInput(attrs={"type": "date"}),
            "teaching_end_date": forms.DateInput(attrs={"type": "date"}),
            "submission_start_date": forms.DateInput(attrs={"type": "date"}),
            "submission_end_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "year": "Ano",
            "period": "Período",
            "teaching_start_date": "Data inicial",
            "teaching_end_date": "Data final",
            "submission_start_date": "Data inicial das inscrições",
            "submission_end_date": "Data final das inscrições",
        }

    def clean(self):
        cleaned = super().clean()
        self._validate_period(
            cleaned,
            start_field="teaching_start_date",
            end_field="teaching_end_date",
        )
        self._validate_period(
            cleaned,
            start_field="submission_start_date",
            end_field="submission_end_date",
        )
        return cleaned

    def _validate_period(self, cleaned, *, start_field: str, end_field: str) -> None:
        start = cleaned.get(start_field)
        end = cleaned.get(end_field)
        if start and end and end < start:
            self.add_error(
                end_field,
                "A data final não pode ser anterior à data inicial.",
            )
