import secrets
from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction

from files.models import FileAsset
from files.services import create_file_asset

from .models import (
    ApplicationAttachment,
    ApplicationCatalogSelection,
    CatalogOption,
    ServiceApplication,
)

MAX_PROTOCOL_ATTEMPTS = 10

User = get_user_model()


class ProtocolGenerationError(RuntimeError):
    """Erro quando não é possível gerar um protocolo único."""


class ProtocolGenerator:
    """Gera protocolos de 9 dígitos únicos (preenchidos com zeros à esquerda)."""

    def __init__(self, model: type[ServiceApplication] = ServiceApplication) -> None:
        self.model = model

    def generate(self) -> str:
        for _ in range(100):
            protocol = f"{secrets.randbelow(1_000_000_000):09d}"
            if not self.model.objects.all_with_deleted().filter(protocol=protocol).exists():
                return protocol
        raise ProtocolGenerationError("Não foi possível gerar um protocolo único.")


class ApplicationSubmissionService:
    """Serviço de domínio responsável por criar inscrições."""

    def __init__(self, protocol_generator: ProtocolGenerator | None = None) -> None:
        self.protocol_generator = protocol_generator or ProtocolGenerator()

    def create_application(
        self,
        *,
        term: Any,
        owner: Any,
        modality: str,
        researcher_name: str,
        contact_email: str,
        contact_phone: str | None = None,
        has_whatsapp: bool = False,
        tax_id: str | None = None,
        institution_name: str | None = None,
        course_name: str | None = None,
        mentor_name: str | None = None,
        project_title: str | None = None,
        context_summary: str | None = None,
        general_objectives: str | None = None,
        variables_and_measurements: str | None = None,
        contextual_factors: str | None = None,
        sampling_and_limitations: str | None = None,
        data_management_plan: str | None = None,
        expected_results: str | None = None,
        expected_support: str | None = None,
        data_already_collected: bool | None = None,
        data_use_authorization_accepted: bool = False,
        mentor_declaration_accepted: bool = False,
        wants_refund_receipt: bool = False,
        refund_receipt_details: str | None = None,
        catalog_option_ids: list[int] | None = None,
        catalog_other_text: str | None = None,
        attachments: list[UploadedFile] | None = None,
    ) -> ServiceApplication:
        dataset_audit_required = modality == ServiceApplication.Modality.PROJECT and owner is not None
        lifecycle_status = (
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION
            if modality == ServiceApplication.Modality.PROJECT
            else ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
        )
        dataset_audit_state = (
            ServiceApplication.DatasetAuditState.AWAITING_SUBMISSION
            if dataset_audit_required
            else None
        )
        base_values: dict[str, Any] = {
            "term": term,
            "owner": owner,
            "modality": modality,
            "origin": ServiceApplication.Origin.CREATED_PORTAL,
            "lifecycle_status": lifecycle_status,
            "dataset_audit_required": dataset_audit_required,
            "dataset_audit_state": dataset_audit_state,
            "researcher_name": researcher_name,
            "contact_email": contact_email,
            "has_whatsapp": has_whatsapp,
            "data_use_authorization_accepted": data_use_authorization_accepted,
            "mentor_declaration_accepted": mentor_declaration_accepted,
            "wants_refund_receipt": wants_refund_receipt,
        }
        optional_values: dict[str, Any] = {
            "contact_phone": contact_phone,
            "tax_id": tax_id,
            "institution_name": institution_name,
            "course_name": course_name,
            "mentor_name": mentor_name,
            "project_title": project_title,
            "context_summary": context_summary,
            "general_objectives": general_objectives,
            "variables_and_measurements": variables_and_measurements,
            "contextual_factors": contextual_factors,
            "sampling_and_limitations": sampling_and_limitations,
            "data_management_plan": data_management_plan,
            "expected_results": expected_results,
            "expected_support": expected_support,
            "data_already_collected": data_already_collected,
            "refund_receipt_details": refund_receipt_details,
        }
        values = {**base_values, **{k: v for k, v in optional_values.items() if v is not None}}

        application: ServiceApplication | None = None
        for _ in range(MAX_PROTOCOL_ATTEMPTS):
            protocol = self.protocol_generator.generate()
            try:
                with transaction.atomic():
                    application = ServiceApplication.objects.create(protocol=protocol, **values)
            except IntegrityError:
                continue
            break
        if application is None:
            raise ProtocolGenerationError("Não foi possível gerar um protocolo único.")

        self._add_catalog_selections(application, catalog_option_ids or [], catalog_other_text)
        for uploaded_file in attachments or []:
            self._add_attachment(application, owner, uploaded_file)
        return application

    def _add_catalog_selections(
        self,
        application: ServiceApplication,
        option_ids: list[int],
        other_text: str | None,
    ) -> None:
        other_ids = set(CatalogOption.objects.filter(id__in=option_ids, code="other").values_list("id", flat=True))
        for option_id in option_ids:
            ApplicationCatalogSelection.objects.create(
                application=application,
                option_id=option_id,
                other_text=other_text if option_id in other_ids else None,
            )

    def _add_attachment(
        self,
        application: ServiceApplication,
        uploaded_by: Any,
        uploaded_file: UploadedFile,
    ) -> None:
        file_asset = create_file_asset(
            application=application,
            uploaded_by=uploaded_by,
            uploaded_file=uploaded_file,
            purpose=FileAsset.Purpose.APPLICATION_ATTACHMENT,
        )
        ApplicationAttachment.objects.create(application=application, file_asset=file_asset)
