import re
from typing import Any
from urllib.parse import urlparse

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from applications.models import ServiceApplication
from files.models import FileAsset
from files.services import create_file_asset
from payments.services import FeeCalculationService
from terms.models import AcademicTerm

from .models import (
    DatasetAuditResolution,
    DatasetAuditReview,
    DatasetAuditSubmission,
)

MAX_DATASET_FILE_SIZE = 10 * 1024 * 1024

URL_MAX_LENGTH = 2048

_VALID_SUBMISSION_STATUSES = {
    ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
    ServiceApplication.LifecycleStatus.AWAITING_DATASET_CORRECTION,
}

_URL_PATH_SAFE_RE = re.compile(r"^[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*$")


class DatasetAuditError(ValueError):
    """Erro de domínio para falhas de validação no fluxo de auditoria."""


def validate_external_url(url: str) -> str:
    """Valida o formato seguro de uma URL externa (HTTP/HTTPS) (TS-AUD-006)."""
    if not isinstance(url, str) or not url:
        raise DatasetAuditError("A URL externa é obrigatória para o canal por link.")
    if len(url) > URL_MAX_LENGTH:
        raise DatasetAuditError("A URL externa excede o comprimento máximo permitido.")
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise DatasetAuditError("URL externa malformada.") from exc
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise DatasetAuditError("A URL externa deve utilizar o protocolo HTTP ou HTTPS.")
    if not parsed.netloc:
        raise DatasetAuditError("A URL externa não possui um domínio válido.")
    if not _URL_PATH_SAFE_RE.match(parsed.path or ""):
        raise DatasetAuditError("A URL externa contém caracteres inválidos.")
    return url


class DatasetAuditService:
    """Serviço de domínio responsável pelo fluxo de auditoria de dados."""

    def submit_dataset(
        self,
        *,
        application: ServiceApplication,
        submitted_by: Any,
        channel: str,
        uploaded_file: UploadedFile | None = None,
        external_url: str | None = None,
        external_link_declaration: bool = False,
        note: str | None = None,
    ) -> DatasetAuditSubmission:
        self._assert_submittable(application)
        channel_enum = DatasetAuditSubmission.Channel(channel)

        if channel_enum == DatasetAuditSubmission.Channel.FILE:
            if uploaded_file is None:
                raise DatasetAuditError("Um arquivo é obrigatório para o canal por arquivo.")
            if external_url:
                raise DatasetAuditError(
                    "Não é permitido enviar arquivo e link externo simultaneamente."
                )
            self._assert_file_size(uploaded_file)
            with transaction.atomic():
                file_asset = create_file_asset(
                    application=application,
                    uploaded_by=submitted_by,
                    uploaded_file=uploaded_file,
                    purpose=FileAsset.Purpose.DATASET_SUBMISSION,
                )
                submission = DatasetAuditSubmission.objects.create(
                    application=application,
                    submitted_by=submitted_by,
                    submission_channel=channel_enum.value,
                    file_asset=file_asset,
                    external_url=None,
                    external_link_declaration=False,
                    note=note,
                    state=DatasetAuditSubmission.State.SUBMITTED,
                )
                self._move_to_review(application)
        elif channel_enum == DatasetAuditSubmission.Channel.EXTERNAL_LINK:
            if external_link_declaration is not True:
                raise DatasetAuditError(
                    "É obrigatório declarar que o link externo está acessível."
                )
            if uploaded_file is not None:
                raise DatasetAuditError(
                    "Não é permitido enviar arquivo e link externo simultaneamente."
                )
            safe_url = validate_external_url(external_url or "")
            with transaction.atomic():
                submission = DatasetAuditSubmission.objects.create(
                    application=application,
                    submitted_by=submitted_by,
                    submission_channel=channel_enum.value,
                    file_asset=None,
                    external_url=safe_url,
                    external_link_declaration=True,
                    note=note,
                    state=DatasetAuditSubmission.State.SUBMITTED,
                )
                self._move_to_review(application)
        else:  # pragma: no cover - protegido pela enum
            raise DatasetAuditError(f"Canal de submissão inválido: {channel}.")
        return submission

    def review_submission(
        self,
        *,
        submission: DatasetAuditSubmission,
        reviewer: Any,
        outcome: str,
        note: str | None = None,
    ) -> DatasetAuditReview:
        outcome_enum = DatasetAuditReview.Outcome(outcome)
        application = submission.application
        if application.lifecycle_status != ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW:
            raise DatasetAuditError(
                "Apenas submissões em análise podem ser revisadas."
            )
        self._assert_submission_not_reviewed(submission)
        now = timezone.now()
        with transaction.atomic():
            review = DatasetAuditReview.objects.create(
                submission=submission,
                reviewer=reviewer,
                outcome=outcome_enum.value,
                note=note,
                reviewed_at=now,
            )
            self._apply_review_outcome(submission, application, outcome_enum)
        return review

    def resolve_rejection(
        self,
        *,
        submission: DatasetAuditSubmission,
        decided_by: Any,
        resolution: str,
        note: str | None = None,
        target_term: AcademicTerm | None = None,
    ) -> DatasetAuditResolution:
        resolution_enum = DatasetAuditResolution.Resolution(resolution)
        application = submission.application
        if application.lifecycle_status != (
            ServiceApplication.LifecycleStatus.DATASET_REJECTED_PENDING_RESOLUTION
        ):
            raise DatasetAuditError(
                "Apenas inscrições rejeitadas pendentes de decisão podem ser resolvidas."
            )
        now = timezone.now()
        with transaction.atomic():
            resolution_record = DatasetAuditResolution.objects.create(
                submission=submission,
                application=application,
                target_term=(
                    target_term
                    if resolution_enum == DatasetAuditResolution.Resolution.TRANSFER_TERM
                    else None
                ),
                decided_by=decided_by,
                resolution=resolution_enum.value,
                note=note,
                decided_at=now,
            )
            self._apply_resolution(application, resolution_enum, target_term)
        return resolution_record

    def enable_audit(self, *, application: ServiceApplication) -> None:
        """Habilita manualmente a auditoria (TS-AUD-016)."""
        if application.owner_id is None:
            raise DatasetAuditError(
                "A auditoria só pode ser habilitada para inscrições com dono."
            )
        if application.modality != ServiceApplication.Modality.PROJECT:
            raise DatasetAuditError(
                "A auditoria só se aplica a inscrições da modalidade Projeto."
            )
        with transaction.atomic():
            application.dataset_audit_required = True
            application.dataset_audit_state = (
                ServiceApplication.DatasetAuditState.AWAITING_SUBMISSION
            )
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION
            )
            application.save(
                update_fields=[
                    "dataset_audit_required",
                    "dataset_audit_state",
                    "lifecycle_status",
                    "updated_at",
                ]
            )

    def _assert_submittable(self, application: ServiceApplication) -> None:
        if application.modality != ServiceApplication.Modality.PROJECT:
            raise DatasetAuditError("Apenas inscrições da modalidade Projeto aceitam auditoria.")
        if application.owner_id is None:
            raise DatasetAuditError("Inscrições sem dono não entram em auditoria.")
        if application.lifecycle_status not in _VALID_SUBMISSION_STATUSES:
            raise DatasetAuditError(
                "A inscrição não está em estado que permita envio de dados para auditoria."
            )
        if not application.dataset_audit_required:
            raise DatasetAuditError("A auditoria não está habilitada para esta inscrição.")

    def _assert_file_size(self, uploaded_file: UploadedFile) -> None:
        size = getattr(uploaded_file, "size", 0) or 0
        if size <= 0:
            raise DatasetAuditError("O arquivo enviado está vazio.")
        if size > MAX_DATASET_FILE_SIZE:
            raise DatasetAuditError("O arquivo excede o limite máximo de 10 MB.")

    def _assert_submission_not_reviewed(self, submission: DatasetAuditSubmission) -> None:
        if submission.reviews.exists():
            raise DatasetAuditError("Esta submissão já foi revisada.")

    def _move_to_review(self, application: ServiceApplication) -> None:
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_REVIEW
        )
        application.dataset_audit_state = (
            ServiceApplication.DatasetAuditState.AWAITING_REVIEW
        )
        application.save(update_fields=["lifecycle_status", "dataset_audit_state", "updated_at"])

    def _apply_review_outcome(
        self,
        submission: DatasetAuditSubmission,
        application: ServiceApplication,
        outcome_enum: DatasetAuditReview.Outcome,
    ) -> None:
        if outcome_enum == DatasetAuditReview.Outcome.NEEDS_CORRECTION:
            submission.state = DatasetAuditSubmission.State.NEEDS_CORRECTION
            submission.save(update_fields=["state", "updated_at"])
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_DATASET_CORRECTION
            )
            application.dataset_audit_state = (
                ServiceApplication.DatasetAuditState.NEEDS_CORRECTION
            )
        elif outcome_enum == DatasetAuditReview.Outcome.APPROVED:
            submission.state = DatasetAuditSubmission.State.APPROVED
            submission.save(update_fields=["state", "updated_at"])
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
            )
            application.dataset_audit_state = (
                ServiceApplication.DatasetAuditState.APPROVED
            )
            FeeCalculationService().create_application_fee(application)
        else:  # rejected
            submission.state = DatasetAuditSubmission.State.REJECTED
            submission.save(update_fields=["state", "updated_at"])
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.DATASET_REJECTED_PENDING_RESOLUTION
            )
            application.dataset_audit_state = (
                ServiceApplication.DatasetAuditState.REJECTED_PENDING_RESOLUTION
            )
        application.save(
            update_fields=["lifecycle_status", "dataset_audit_state", "updated_at"]
        )

    def _apply_resolution(
        self,
        application: ServiceApplication,
        resolution_enum: DatasetAuditResolution.Resolution,
        target_term: AcademicTerm | None,
    ) -> None:
        if resolution_enum == DatasetAuditResolution.Resolution.CONVERT_TO_CONSULTATION:
            application.modality = ServiceApplication.Modality.CONSULTATION
            application.dataset_audit_required = False
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
            )
            application.dataset_audit_state = None
            application.save(
                update_fields=[
                    "modality",
                    "dataset_audit_required",
                    "lifecycle_status",
                    "dataset_audit_state",
                    "updated_at",
                ]
            )
            FeeCalculationService().create_application_fee(application)
        elif resolution_enum == DatasetAuditResolution.Resolution.REJECT_APPLICATION:
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.NOT_APPROVED
            )
            application.save(update_fields=["lifecycle_status", "updated_at"])
        else:  # transfer_term
            if target_term is None:
                raise DatasetAuditError("Um período alvo é obrigatório para a transferência.")
            application.term = target_term
            application.save(update_fields=["term", "updated_at"])
