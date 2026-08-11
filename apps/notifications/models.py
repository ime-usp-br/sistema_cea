from django.db import models


class NotificationTemplate(models.Model):
    """Template canônico de e-mail usado para disparos de notificação."""

    class Audience(models.TextChoices):
        CANDIDATE = "candidate", "Candidato"
        CENTER = "center", "Equipe CEA"
        TEACHER = "teacher", "Docente"
        SECRETARIAT = "secretariat", "Secretaria"

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    audience = models.CharField(max_length=30, choices=Audience.choices)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    audience__in=["candidate", "center", "teacher", "secretariat"]
                ),
                name="chk_notification_templates_audience",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_audience_display()})"


class NotificationDispatch(models.Model):
    """Registro de um despacho de e-mail enviado para um destinatário."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falhou"

    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.RESTRICT,
        related_name="dispatches",
    )
    application = models.ForeignKey(
        "applications.ServiceApplication",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_dispatches",
    )
    recipient_email = models.EmailField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    error_message = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_dispatches"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "sent", "failed"]),
                name="chk_notification_dispatches_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.template.code} -> {self.recipient_email} ({self.status})"
