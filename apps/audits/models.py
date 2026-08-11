from django.conf import settings
from django.db import models


class DatasetAuditSubmission(models.Model):
    """Submissão de dados para auditoria (Fluxo do Docente)."""

    class Channel(models.TextChoices):
        FILE = "file", "Arquivo"
        EXTERNAL_LINK = "external_link", "Link externo"

    class State(models.TextChoices):
        SUBMITTED = "submitted", "Enviada"
        NEEDS_CORRECTION = "needs_correction", "Correção necessária"
        APPROVED = "approved", "Aprovada"
        REJECTED = "rejected", "Rejeitada"

    application = models.ForeignKey(
        "applications.ServiceApplication",
        on_delete=models.RESTRICT,
        related_name="audit_submissions",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_submissions",
    )
    submission_channel = models.CharField(max_length=20, choices=Channel.choices)
    file_asset = models.ForeignKey(
        "files.FileAsset",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="audit_submissions",
    )
    external_url = models.CharField(max_length=2048, null=True, blank=True)
    external_link_declaration = models.BooleanField(default=False)
    note = models.TextField(null=True, blank=True)
    state = models.CharField(max_length=30, choices=State.choices, default=State.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dataset_audit_submissions"
        ordering = ["-submitted_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(submission_channel__in=["file", "external_link"]),
                name="chk_audit_submissions_channel",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        submission_channel="file",
                        file_asset__isnull=False,
                        external_url__isnull=True,
                    )
                    | models.Q(
                        submission_channel="external_link",
                        external_url__isnull=False,
                        file_asset__isnull=True,
                        external_link_declaration=True,
                    )
                ),
                name="chk_audit_submissions_single_channel",
            ),
        ]

    def __str__(self) -> str:
        return f"Submissão #{self.pk} ({self.submission_channel})"


class DatasetAuditReview(models.Model):
    """Revisão docente de uma submissão de auditoria."""

    class Outcome(models.TextChoices):
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Rejeitado"
        NEEDS_CORRECTION = "needs_correction", "Correção solicitada"

    submission = models.ForeignKey(
        DatasetAuditSubmission,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_reviews",
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    note = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dataset_audit_reviews"
        constraints = [
            models.UniqueConstraint(
                fields=["submission"],
                name="uq_dataset_audit_reviews_submission",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    outcome__in=["approved", "rejected", "needs_correction"]
                ),
                name="chk_audit_reviews_outcome",
            ),
        ]

    def __str__(self) -> str:
        return f"Revisão #{self.pk} ({self.outcome})"


class DatasetAuditResolution(models.Model):
    """Decisão administrativa da secretaria sobre auditoria rejeitada."""

    class Resolution(models.TextChoices):
        CONVERT_TO_CONSULTATION = "convert_to_consultation", "Converter em consulta"
        REJECT_APPLICATION = "reject_application", "Rejeitar inscrição"
        TRANSFER_TERM = "transfer_term", "Transferir de período"

    submission = models.ForeignKey(
        DatasetAuditSubmission,
        on_delete=models.CASCADE,
        related_name="resolutions",
    )
    application = models.ForeignKey(
        "applications.ServiceApplication",
        on_delete=models.RESTRICT,
        related_name="audit_resolutions",
    )
    target_term = models.ForeignKey(
        "terms.AcademicTerm",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="audit_resolutions",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_resolutions",
    )
    resolution = models.CharField(max_length=30, choices=Resolution.choices)
    note = models.TextField(null=True, blank=True)
    decided_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dataset_audit_resolutions"
        constraints = [
            models.UniqueConstraint(
                fields=["submission"],
                name="uq_dataset_audit_resolutions_submission",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    resolution__in=[
                        "convert_to_consultation",
                        "reject_application",
                        "transfer_term",
                    ]
                ),
                name="chk_audit_resolutions_resolution",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(resolution="transfer_term", target_term__isnull=False)
                    | models.Q(resolution="convert_to_consultation", target_term__isnull=True)
                    | models.Q(resolution="reject_application", target_term__isnull=True)
                ),
                name="chk_audit_resolutions_transfer_requires_term",
            ),
        ]

    def __str__(self) -> str:
        return f"Resolução #{self.pk} ({self.resolution})"
