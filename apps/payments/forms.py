from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator

from .models import PaymentInstrument


class PaymentMethodForm(forms.Form):
    """Candidato escolhe a forma de pagamento (Pix ou Boleto)."""

    method = forms.ChoiceField(
        choices=[
            (PaymentInstrument.Method.PIX, "Pix"),
            (PaymentInstrument.Method.BANK_SLIP, "Boleto"),
        ],
        label="Forma de pagamento",
    )


class ManualPaymentConfirmationForm(forms.Form):
    """Secretaria confirma um pagamento manual."""

    note = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Observação",
    )


class RefundRequestForm(forms.Form):
    """Secretaria solicita um reembolso."""

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Valor do reembolso (R$)",
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    reason = forms.CharField(widget=forms.Textarea, required=False, label="Motivo")
