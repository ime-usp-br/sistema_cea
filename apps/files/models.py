import uuid

from django.conf import settings
from django.db import models


class FileAsset(models.Model):
    """Metadados centrais de arquivos, referenciando caminhos no Storage/S3."""

    class Purpose(models.TextChoices):
        APPLICATION_ATTACHMENT = "application_attachment", "Anexo da inscrição"
        DATASET_SUBMISSION = "dataset_submission", "Arquivo de auditoria"
        PAYMENT_RECEIPT = "payment_receipt", "Comprovante"
        PIX_QRCODE_IMAGE = "pix_qrcode_image", "Imagem QR"
        PIX_PDF = "pix_pdf", "PDF do Pix"
        BANK_SLIP_PDF = "bank_slip_pdf", "PDF do boleto"
        DOCUMENT_EXPORT = "document_export", "Documento gerado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=255, unique=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    sha256_checksum = models.CharField(max_length=64, null=True, blank=True)
    purpose = models.CharField(max_length=50, choices=Purpose.choices)
    application = models.ForeignKey(
        "applications.ServiceApplication",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="file_assets",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_file_assets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "file_assets"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(size_bytes__gte=0) | models.Q(size_bytes__isnull=True),
                name="chk_file_assets_size",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.purpose})"
