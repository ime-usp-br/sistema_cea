from django.db import models


class BankSlipPaymentInstrument(models.Model):
    """Boleto registrado no serviço externo (SOAP/WSDL)."""

    class BankStatus(models.TextChoices):
        EMITTED = "E", "Emitido"
        PAID = "P", "Pago"
        VERIFY = "V", "Verificar"
        CANCELED = "C", "Cancelado"

    payment_instrument = models.OneToOneField(
        "payments.PaymentInstrument",
        on_delete=models.CASCADE,
        related_name="bank_slip_instrument",
    )
    bank_slip_reference = models.CharField(max_length=60, unique=True)
    due_date = models.DateField(null=True, blank=True)
    bank_status = models.CharField(max_length=1, choices=BankStatus.choices, default=BankStatus.EMITTED)
    document_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    cancellation_date = models.DateField(null=True, blank=True)
    pdf_asset = models.ForeignKey(
        "files.FileAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_slips",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_slip_payment_instruments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Boleto {self.bank_slip_reference}"
