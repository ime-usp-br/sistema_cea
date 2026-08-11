from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q, Sum


class FeeRequirement(models.Model):
    """Taxa devida por uma inscrição (base do sistema financeiro)."""

    class FeeType(models.TextChoices):
        APPLICATION_FEE = "application_fee", "Taxa de inscrição"
        PROJECT_FEE = "project_fee", "Taxa de projeto"
        SUPPLEMENT_FEE = "supplement_fee", "Taxa complementar"

    application = models.ForeignKey(
        "applications.ServiceApplication",
        on_delete=models.RESTRICT,
        related_name="fee_requirements",
    )
    fee_type = models.CharField(max_length=30, choices=FeeType.choices)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    adjustment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    adjustment_reason = models.CharField(max_length=255, null=True, blank=True)
    reason = models.CharField(max_length=255)
    is_waived = models.BooleanField(default=False)
    waiver_reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fee_requirements"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fee_type__in=["application_fee", "project_fee", "supplement_fee"]),
                name="chk_fee_requirements_fee_type",
            ),
            models.CheckConstraint(
                condition=Q(amount=F("base_amount") + F("adjustment_amount")),
                name="chk_fee_requirements_amount",
            ),
        ]

    @property
    def is_paid(self) -> bool:
        return self.payment_instruments.filter(
            state__in=[PaymentInstrument.State.PAID, PaymentInstrument.State.MANUAL_CONFIRMED]
        ).exists()

    @property
    def paid_amount(self) -> Decimal:
        total = (
            self.payment_instruments.filter(
                state__in=[PaymentInstrument.State.PAID, PaymentInstrument.State.MANUAL_CONFIRMED]
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        return Decimal(str(total))

    def __str__(self) -> str:
        return f"{self.get_fee_type_display()} R$ {self.amount}"


class PaymentInstrument(models.Model):
    """Instância/tentativa de pagamento atrelada a uma taxa."""

    class Method(models.TextChoices):
        PIX = "pix", "Pix"
        BANK_SLIP = "bank_slip", "Boleto"
        MANUAL = "manual", "Manual"

    class State(models.TextChoices):
        CREATED = "created", "Criado"
        ACTIVE = "active", "Ativo"
        PAID = "paid", "Pago"
        EXPIRED = "expired", "Expirado"
        CANCELED = "canceled", "Cancelado"
        SUPERSEDED = "superseded", "Substituído"
        FAILED = "failed", "Falhou"
        MANUAL_CONFIRMED = "manual_confirmed", "Confirmado manualmente"
        REQUIRES_REVIEW = "requires_review", "Exige revisão"

    fee_requirement = models.ForeignKey(
        FeeRequirement,
        on_delete=models.RESTRICT,
        related_name="payment_instruments",
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    state = models.CharField(max_length=30, choices=State.choices, default=State.CREATED)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_instruments",
    )
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_instruments",
    )
    active_unique_fee_token = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_instruments"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(method__in=["pix", "bank_slip", "manual"]),
                name="chk_payment_instruments_method",
            ),
            models.CheckConstraint(
                condition=Q(
                    state__in=[
                        "created",
                        "active",
                        "paid",
                        "expired",
                        "canceled",
                        "superseded",
                        "failed",
                        "manual_confirmed",
                        "requires_review",
                    ]
                ),
                name="chk_payment_instruments_state",
            ),
            models.UniqueConstraint(
                fields=["active_unique_fee_token"],
                name="uq_payment_instruments_active_token",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_method_display()} #{self.pk} ({self.state})"


class ManualPaymentConfirmation(models.Model):
    """Confirmação administrativa de pagamento manual."""

    payment_instrument = models.OneToOneField(
        PaymentInstrument,
        on_delete=models.CASCADE,
        related_name="manual_confirmation",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manual_payment_confirmations",
    )
    confirmed_at = models.DateTimeField()
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "manual_payment_confirmations"

    def __str__(self) -> str:
        return f"Confirmação #{self.pk} (instrumento {self.payment_instrument_id})"


class RefundRequest(models.Model):
    """Solicitação de reembolso administrativo."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Solicitado"
        APPROVED = "approved", "Aprovado"
        EXECUTED = "executed", "Executado"
        DENIED = "denied", "Negado"

    application = models.ForeignKey(
        "applications.ServiceApplication",
        on_delete=models.RESTRICT,
        related_name="refund_requests",
    )
    payment_instrument = models.ForeignKey(
        PaymentInstrument,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="refund_requests",
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REQUESTED)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_requests_requested",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_requests_approved",
    )
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refund_requests_executed",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "refund_requests"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["requested", "approved", "executed", "denied"]),
                name="chk_refund_requests_status",
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=Decimal("0.00")),
                name="chk_refund_requests_amount",
            ),
        ]

    def __str__(self) -> str:
        return f"Reembolso #{self.pk} ({self.status})"
