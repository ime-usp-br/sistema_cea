from django.conf import settings
from django.db import models
from django.utils import timezone


class ServiceApplicationQuerySet(models.QuerySet):
    def alive(self) -> ServiceApplicationQuerySet:
        return self.filter(soft_deleted_at__isnull=True)


class ServiceApplicationManager(models.Manager["ServiceApplication"]):
    def get_queryset(self) -> ServiceApplicationQuerySet:
        return ServiceApplicationQuerySet(self.model, using=self._db).alive()

    def all_with_deleted(self) -> ServiceApplicationQuerySet:
        return ServiceApplicationQuerySet(self.model, using=self._db)


class CatalogOption(models.Model):
    """Opções de catálogo para campos de múltipla escolha."""

    class Category(models.TextChoices):
        INSTITUTIONAL_TIE = "institutional_tie", "Vínculo com a Instituição"
        PROJECT_PURPOSE = "project_purpose", "Finalidade do projeto"
        KNOWLEDGE_AREA = "knowledge_area", "Área de conhecimento"
        FUNDING_AGENCY = "funding_agency", "Agência financiadora do projeto"

    id = models.SmallAutoField(primary_key=True)
    category = models.CharField(max_length=50, choices=Category.choices)
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_options"
        ordering = ["category", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "code"],
                name="uq_catalog_options_category_code",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    category__in=[
                        "institutional_tie",
                        "project_purpose",
                        "knowledge_area",
                        "funding_agency",
                    ]
                ),
                name="chk_catalog_options_category",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.category})"


class ServiceApplication(models.Model):
    """Tabela central de inscrições."""

    class Modality(models.TextChoices):
        PROJECT = "project", "Projeto"
        CONSULTATION = "consultation", "Consulta"

    class LifecycleStatus(models.TextChoices):
        SUBMITTED = "submitted", "Submetida"
        AWAITING_DATASET_SUBMISSION = "awaiting_dataset_submission", "Aguardando envio de dados"
        AWAITING_DATASET_REVIEW = "awaiting_dataset_review", "Aguardando análise de dados"
        AWAITING_DATASET_CORRECTION = "awaiting_dataset_correction", "Aguardando correção de dados"
        DATASET_REJECTED_PENDING_RESOLUTION = (
            "dataset_rejected_pending_resolution",
            "Dados rejeitados — aguardando decisão",
        )
        AWAITING_PAYMENT = "awaiting_payment", "Aguardando pagamento"
        AWAITING_SCREENING_SCHEDULING = "awaiting_screening_scheduling", "Aguardando agendamento da triagem"
        AWAITING_SCREENING_RESULT = "awaiting_screening_result", "Aguardando resultado da triagem"
        AWAITING_CONSULTATION_SCHEDULING = (
            "awaiting_consultation_scheduling",
            "Aguardando agendamento da reunião de consulta",
        )
        AWAITING_CONSULTATION_RESULT = (
            "awaiting_consultation_result",
            "Aguardando resultado da reunião de consulta",
        )
        APPROVED_AS_PROJECT = "approved_as_project", "Aprovado como projeto"
        APPROVED_AS_CONSULTATION = "approved_as_consultation", "Aprovado como consulta"
        NOT_APPROVED = "not_approved", "Não aprovado"
        TRANSFERRED = "transferred", "Transferida"
        CANCELED = "canceled", "Cancelada"

    # TODO(AI-Assumption): payment_state e dataset_audit_state terão a máquina
    # de estados definitiva definida nas Fases 4 e 5. Os valores abaixo são
    # provisórios para dar estabilidade ao modelo nesta fase.
    class PaymentState(models.TextChoices):
        PENDING = "pending", "Pendente"
        PARTIALLY_PAID = "partially_paid", "Parcialmente pago"
        PAID = "paid", "Pago"
        REFUNDED = "refunded", "Reembolsado"

    class DatasetAuditState(models.TextChoices):
        NOT_REQUIRED = "not_required", "Não exigida"
        AWAITING_SUBMISSION = "awaiting_submission", "Aguardando envio"
        AWAITING_REVIEW = "awaiting_review", "Aguardando análise"
        NEEDS_CORRECTION = "needs_correction", "Correção necessária"
        REJECTED_PENDING_RESOLUTION = "rejected_pending_resolution", "Rejeitada — aguardando decisão"
        APPROVED = "approved", "Aprovada"

    class Origin(models.TextChoices):
        CREATED_PORTAL = "created_portal", "Criada no portal"
        IMPORTED = "imported", "Importada"

    class RefundAccountType(models.TextChoices):
        CHECKING = "checking", "Conta corrente"
        SAVINGS = "savings", "Conta poupança"

    term = models.ForeignKey(
        "terms.AcademicTerm",
        on_delete=models.RESTRICT,
        related_name="applications",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="applications",
    )

    protocol = models.CharField(max_length=9)
    modality = models.CharField(max_length=20, choices=Modality.choices)
    lifecycle_status = models.CharField(
        max_length=60,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.SUBMITTED,
    )
    payment_state = models.CharField(
        max_length=30,
        choices=PaymentState.choices,
        null=True,
        blank=True,
    )

    dataset_audit_required = models.BooleanField(default=False)
    dataset_audit_state = models.CharField(
        max_length=40,
        choices=DatasetAuditState.choices,
        null=True,
        blank=True,
    )

    origin = models.CharField(
        max_length=20,
        choices=Origin.choices,
        default=Origin.CREATED_PORTAL,
    )
    modality_credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    transfer_pending = models.BooleanField(default=False)
    transfer_reason = models.TextField(null=True, blank=True)

    researcher_name = models.CharField(max_length=255)
    contact_email = models.EmailField(max_length=255)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)
    has_whatsapp = models.BooleanField(default=False)
    tax_id = models.CharField(max_length=20, null=True, blank=True)

    institution_name = models.CharField(max_length=255, null=True, blank=True)
    course_name = models.CharField(max_length=255, null=True, blank=True)
    mentor_name = models.CharField(max_length=255, null=True, blank=True)

    wants_refund_receipt = models.BooleanField(default=False)
    refund_receipt_details = models.TextField(null=True, blank=True)

    refund_account_holder_name = models.CharField(max_length=255, null=True, blank=True)
    refund_account_holder_tax_id = models.CharField(max_length=20, null=True, blank=True)
    refund_bank_name = models.CharField(max_length=255, null=True, blank=True)
    refund_branch_number = models.CharField(max_length=50, null=True, blank=True)
    refund_bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    refund_bank_account_type = models.CharField(
        max_length=20,
        choices=RefundAccountType.choices,
        null=True,
        blank=True,
    )

    project_title = models.TextField(null=True, blank=True)
    context_summary = models.TextField(null=True, blank=True)
    general_objectives = models.TextField(null=True, blank=True)
    variables_and_measurements = models.TextField(null=True, blank=True)
    contextual_factors = models.TextField(null=True, blank=True)
    sampling_and_limitations = models.TextField(null=True, blank=True)
    data_management_plan = models.TextField(null=True, blank=True)
    expected_results = models.TextField(null=True, blank=True)
    expected_support = models.TextField(null=True, blank=True)
    data_already_collected = models.BooleanField(null=True, blank=True)

    data_use_authorization_accepted = models.BooleanField(null=True, blank=True)
    mentor_declaration_accepted = models.BooleanField(null=True, blank=True)

    legacy_contact_email = models.CharField(max_length=255, null=True, blank=True)
    legacy_contact_tax_id = models.CharField(max_length=20, null=True, blank=True)

    soft_deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceApplicationManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "service_applications"
        ordering = ["-created_at"]
        base_manager_name = "all_objects"
        indexes = [
            models.Index(fields=["term"], name="idx_svc_applications_term"),
            models.Index(fields=["owner"], name="idx_svc_applications_owner"),
            models.Index(fields=["protocol"], name="idx_svc_applications_protocol"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["protocol"], name="uq_service_applications_protocol"),
            models.CheckConstraint(
                condition=models.Q(modality__in=["project", "consultation"]),
                name="chk_service_applications_modality",
            ),
            models.CheckConstraint(
                condition=models.Q(origin__in=["created_portal", "imported"]),
                name="chk_service_applications_origin",
            ),
            models.CheckConstraint(
                condition=models.Q(modality_credit_amount__gte=0),
                name="chk_service_applications_modality_credit",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.protocol} - {self.get_modality_display()}"

    def soft_delete(self) -> None:
        self.soft_deleted_at = timezone.now()
        self.save(update_fields=["soft_deleted_at", "updated_at"])

    def restore(self) -> None:
        self.soft_deleted_at = None
        self.save(update_fields=["soft_deleted_at", "updated_at"])


class ApplicationCatalogSelection(models.Model):
    """Relaciona inscrições com opções de catálogo."""

    application = models.ForeignKey(
        ServiceApplication,
        on_delete=models.CASCADE,
        related_name="catalog_selections",
    )
    option = models.ForeignKey(
        CatalogOption,
        on_delete=models.RESTRICT,
        related_name="application_selections",
    )
    other_text = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "application_catalog_selections"
        constraints = [
            models.UniqueConstraint(
                fields=["application", "option"],
                name="uq_application_catalog_selections",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.application_id} - {self.option}"


class ApplicationAttachment(models.Model):
    """Anexos manuais de inscrição."""

    application = models.ForeignKey(
        ServiceApplication,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file_asset = models.ForeignKey(
        "files.FileAsset",
        on_delete=models.CASCADE,
        related_name="application_attachment",
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "application_attachments"
        constraints = [
            models.UniqueConstraint(
                fields=["file_asset"],
                name="uq_application_attachments_file",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.application_id} - {self.file_asset_id}"


class ApplicationEvent(models.Model):
    """Trilha de auditoria de eventos de uma inscrição."""

    application = models.ForeignKey(
        ServiceApplication,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_code = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="application_events",
    )
    metadata = models.JSONField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "application_events"
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.application_id} - {self.event_code}"
