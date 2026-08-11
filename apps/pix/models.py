from django.db import models


class PixPaymentInstrument(models.Model):
    """Cobrança Pix gerada no gateway externo (idfpix)."""

    payment_instrument = models.OneToOneField(
        "payments.PaymentInstrument",
        on_delete=models.CASCADE,
        related_name="pix_instrument",
    )
    pix_reference = models.CharField(max_length=35, unique=True)
    qr_code_payload = models.CharField(max_length=255)
    qr_code_image_asset = models.ForeignKey(
        "files.FileAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pix_instruments",
    )
    external_status = models.CharField(max_length=20, null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payer_name = models.CharField(max_length=150, null=True, blank=True)
    payer_tax_id = models.CharField(max_length=14, null=True, blank=True)
    bank_return_code = models.CharField(max_length=35, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pix_payment_instruments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Pix {self.pix_reference}"


class PixWebhookEvent(models.Model):
    """Entrega de webhook recebida do gateway Pix (idempotente)."""

    pix_reference = models.CharField(max_length=35)
    raw_payload = models.JSONField()
    token_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pix_webhook_events"
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return f"Webhook {self.pix_reference} (token={self.token_valid})"
