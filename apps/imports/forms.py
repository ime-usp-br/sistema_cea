from typing import Any

from django import forms

from .models import LegacyOwnershipClaim


class ClaimRequestForm(forms.Form):
    protocol = forms.CharField(
        label="Protocolo",
        required=False,
        max_length=9,
        widget=forms.TextInput(attrs={"placeholder": "Opcional, ex.: 123456789"}),
    )
    contact_email_or_tax_id = forms.CharField(
        label="E-mail ou documento",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "E-mail ou CPF/RG cadastrado"}),
    )

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if not cleaned.get("protocol") and not cleaned.get("contact_email_or_tax_id"):
            raise forms.ValidationError(
                "Informe ao menos o protocolo ou e-mail/documento."
            )
        return cleaned


class ClaimConfirmForm(forms.Form):
    code = forms.CharField(
        label="Código de verificação",
        required=True,
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "maxlength": "6"}),
    )


class ManualApprovalForm(forms.ModelForm):
    class Meta:
        model = LegacyOwnershipClaim
        fields = ["review_note"]
        widgets = {"review_note": forms.Textarea(attrs={"rows": 3})}
