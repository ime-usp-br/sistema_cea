from django.conf import settings
from django.db import models


class LegacyOwnershipClaim(models.Model):
    """Reivindicação de posse de uma inscrição legada importada."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        CODE_SENT = "code_sent", "Código enviado"
        VERIFIED = "verified", "Verificada"
        REJECTED = "rejected", "Rejeitada"
        MANUALLY_APPROVED = "manually_approved", "Aprovada manualmente"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_ownership_claims",
    )
    application = models.ForeignKey(
        "applications.ServiceApplication",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ownership_claims",
    )
    protocol = models.CharField(max_length=9, null=True, blank=True)
    contact_email = models.CharField(max_length=255, null=True, blank=True)
    contact_tax_id = models.CharField(max_length=20, null=True, blank=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    verification_token_hash = models.CharField(max_length=255, null=True, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_claims_reviewed",
    )
    review_note = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "legacy_ownership_claims"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["application"], name="idx_legacy_claims_application"),
            models.Index(fields=["status"], name="idx_legacy_claims_status"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "code_sent",
                        "verified",
                        "rejected",
                        "manually_approved",
                    ]
                ),
                name="chk_legacy_ownership_claims_status",
            ),
        ]

    def __str__(self) -> str:
        return f"Claim #{self.pk} ({self.status})"
