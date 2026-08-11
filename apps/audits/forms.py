from django import forms

from .models import DatasetAuditResolution, DatasetAuditReview, DatasetAuditSubmission


class DatasetSubmissionForm(forms.Form):
    """Formulário de envio/correção de dados pelo candidato."""

    channel = forms.ChoiceField(
        choices=DatasetAuditSubmission.Channel.choices,
        label="Canal de envio",
    )
    file = forms.FileField(required=False, label="Arquivo (até 10 MB)")
    external_url = forms.URLField(
        max_length=2048,
        required=False,
        assume_scheme="https",
        label="Link externo (HTTP/HTTPS)",
    )
    external_link_declaration = forms.BooleanField(
        required=False,
        label="Declaro que o link está acessível",
    )
    note = forms.CharField(widget=forms.Textarea, required=False, label="Observação")

    def clean(self):
        cleaned_data = super().clean() or {}
        channel = cleaned_data.get("channel")
        file = cleaned_data.get("file")
        external_url = cleaned_data.get("external_url")
        declaration = cleaned_data.get("external_link_declaration")

        if channel == DatasetAuditSubmission.Channel.FILE.value:
            if not file:
                self.add_error("file", "Envie um arquivo para o canal por arquivo.")
            if external_url:
                self.add_error(
                    "external_url",
                    "Não informe um link ao escolher o canal por arquivo.",
                )
        elif channel == DatasetAuditSubmission.Channel.EXTERNAL_LINK.value:
            if not external_url:
                self.add_error("external_url", "Informe a URL externa.")
            if file:
                self.add_error("file", "Não envie um arquivo ao escolher o canal por link.")
            if not declaration:
                self.add_error(
                    "external_link_declaration",
                    "Confirme a declaração de acesso ao link.",
                )
        return cleaned_data


class DatasetReviewForm(forms.Form):
    """Formulário de análise do docente."""

    outcome = forms.ChoiceField(
        choices=DatasetAuditReview.Outcome.choices,
        label="Decisão",
    )
    note = forms.CharField(widget=forms.Textarea, required=False, label="Observação")


class DatasetResolutionForm(forms.Form):
    """Formulário de decisão administrativa da secretaria."""

    resolution = forms.ChoiceField(
        choices=DatasetAuditResolution.Resolution.choices,
        label="Decisão",
    )
    target_term = forms.IntegerField(required=False, label="ID do período alvo")
    note = forms.CharField(widget=forms.Textarea, required=False, label="Observação")

    def clean(self):
        cleaned_data = super().clean() or {}
        resolution = cleaned_data.get("resolution")
        target_term = cleaned_data.get("target_term")
        if resolution == DatasetAuditResolution.Resolution.TRANSFER_TERM.value and not target_term:
            self.add_error("target_term", "Informe o período alvo para a transferência.")
        return cleaned_data
