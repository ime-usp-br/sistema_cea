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
    ApplicationEvent,
    CatalogOption,
    ServiceApplication,
)

MAX_PROTOCOL_ATTEMPTS = 10

User = get_user_model()


class TermTransferError(RuntimeError):
    """Erro de domínio da transferência de semestre."""


class TermTransferService:
    """Transfere inscrições entre semestres letivos.

    Porta do ``ApplicationController@transferToNextSemester`` (manual) e do
    ``SemesterController::migratePendingApplications`` (automático) do legado.
    A Secretaria transfere inscrições de candidatos cujas triagens atrasaram
    para o próximo período (``transfer_pending``).
    """

    @staticmethod
    def _sort_key(term: Any) -> tuple[int, int]:
        period_rank = 0 if term.period == "first" else 1
        return (term.year, period_rank)

    def find_next_term(self, current_term: Any):
        """Retorna o semestre imediatamente posterior ao atual, ou ``None``."""
        from terms.models import AcademicTerm

        ordered = sorted(AcademicTerm.objects.all(), key=self._sort_key)
        for index, term in enumerate(ordered):
            if term.pk == current_term.pk:
                if index + 1 < len(ordered):
                    return ordered[index + 1]
                break
        return None

    def transfer_to_next_semester(
        self,
        application: ServiceApplication,
        decided_by: Any = None,
        note: str | None = None,
    ) -> ServiceApplication:
        """Transfere a inscrição para o próximo semestre (TS-TRM-001/002).

        Sem próximo semestre disponível, a transferência fica **pendente**
        (``transfer_pending``) em vez de lançar erro; ao criar um novo período,
        :meth:`migrate_pending_applications` conclui a migração (TS-TRM-002/003).
        """
        with transaction.atomic():
            next_term = self.find_next_term(application.term)
            if next_term is None:
                application.transfer_pending = True
                application.transfer_reason = (
                    note
                    or "Não há próximo semestre disponível; transferência pendente."
                )
                application.save(
                    update_fields=["transfer_pending", "transfer_reason", "updated_at"]
                )
                ApplicationEvent.objects.create(
                    application=application,
                    event_code="term.transfer_pending",
                    actor=decided_by,
                    description=application.transfer_reason,
                )
                return application
            application.term = next_term
            application.transfer_pending = False
            application.transfer_reason = None
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.TRANSFERRED
            )
            application.save(
                update_fields=[
                    "term",
                    "transfer_pending",
                    "transfer_reason",
                    "lifecycle_status",
                    "updated_at",
                ]
            )
            ApplicationEvent.objects.create(
                application=application,
                event_code="term.transferred",
                actor=decided_by,
                description=note or f"Inscrição transferida para o semestre {next_term}.",
                metadata={"next_term_id": next_term.pk},
            )
        return application

    def migrate_pending_applications(self, new_term: Any, actor: Any = None) -> int:
        """Move inscrições pendentes para ``new_term`` (TS-TRM-003).

        Disparado ao criar um ``AcademicTerm``: as inscrições com
        ``transfer_pending=True`` são movidas, têm o fluxo reiniciado no
        agendamento (triagem para Projeto; reunião para Consulta) e ganham o
        evento ``term.transfer_auto``. Auditoria, taxas, instrumentos e dono
        permanecem vinculados à inscrição.
        """
        pending = ServiceApplication.objects.filter(transfer_pending=True)
        migrated = 0
        for application in pending:
            with transaction.atomic():
                application.term = new_term
                application.transfer_pending = False
                application.transfer_reason = None
                if application.modality == ServiceApplication.Modality.PROJECT:
                    application.lifecycle_status = (
                        ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
                    )
                else:
                    application.lifecycle_status = (
                        ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
                    )
                application.save(
                    update_fields=[
                        "term",
                        "transfer_pending",
                        "transfer_reason",
                        "lifecycle_status",
                        "updated_at",
                    ]
                )
                ApplicationEvent.objects.create(
                    application=application,
                    event_code="term.transfer_auto",
                    actor=actor,
                    description=(
                        f"Transferência automática para o semestre {new_term}."
                    ),
                    metadata={"new_term_id": new_term.pk},
                )
            migrated += 1
        return migrated


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
        refund_account_holder_name: str | None = None,
        refund_account_holder_tax_id: str | None = None,
        refund_bank_name: str | None = None,
        refund_branch_number: str | None = None,
        refund_bank_account_number: str | None = None,
        refund_bank_account_type: str | None = None,
        catalog_option_ids: list[int] | None = None,
        catalog_other_text: str | None = None,
        attachments: list[UploadedFile] | None = None,
    ) -> ServiceApplication:
        dataset_audit_required = modality == ServiceApplication.Modality.PROJECT and owner is not None
        # Ambas as modalidades começam em awaiting_payment: o candidato paga a
        # taxa de inscrição antes de seguir (auditoria, no caso de Projeto).
        lifecycle_status = ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
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
            "refund_account_holder_name": refund_account_holder_name,
            "refund_account_holder_tax_id": refund_account_holder_tax_id,
            "refund_bank_name": refund_bank_name,
            "refund_branch_number": refund_branch_number,
            "refund_bank_account_number": refund_bank_account_number,
            "refund_bank_account_type": refund_bank_account_type,
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
        from payments.services import FeeCalculationService

        FeeCalculationService().create_application_fee(application)

        # Gatilho do legado ``NotifyInscribedAboutApplication``/``NotifyCEAAboutApplication``
        # (D6): confirma a submissão para o candidato e avisa a equipe CEA.
        from notifications.services import NotificationService

        NotificationService().notify_application_submitted(application)
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
