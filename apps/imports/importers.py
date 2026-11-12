import json
import mimetypes
import os
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.utils import timezone

from applications.models import (
    ApplicationCatalogSelection,
    ApplicationEvent,
    CatalogOption,
    ServiceApplication,
)
from bank_slips.models import BankSlipPaymentInstrument
from files.models import FileAsset
from files.services import create_file_asset_from_bytes
from meetings.models import ConsultationMeeting, ProjectScreening
from payments.models import FeeRequirement, ManualPaymentConfirmation, PaymentInstrument
from terms.models import AcademicTerm

STATE_TO_INSTRUMENT = {
    "created": PaymentInstrument.State.CREATED,
    "active": PaymentInstrument.State.ACTIVE,
    "paid": PaymentInstrument.State.PAID,
    "manual_confirmed": PaymentInstrument.State.MANUAL_CONFIRMED,
    "canceled": PaymentInstrument.State.CANCELED,
    "superseded": PaymentInstrument.State.SUPERSEDED,
    "expired": PaymentInstrument.State.EXPIRED,
    "failed": PaymentInstrument.State.FAILED,
    "requires_review": PaymentInstrument.State.REQUIRES_REVIEW,
}


def _parse_legacy_datetime(value: Any) -> datetime | None:
    """Converte datas do legado (``dd/mm/aaaa``, ISO ou datetime) para aware."""
    if not value:
        return None
    if isinstance(value, datetime):
        parsed: datetime | None = value
    else:
        text = str(value).strip()
        parsed = None
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%Y-%m-%d",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _parse_legacy_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = _parse_legacy_datetime(value)
    return parsed.date() if parsed else None


def _parse_legacy_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value
    text = str(value or "").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    return Decimal(str(value))


def _chronological(items: Any) -> list[dict[str, Any]]:
    """Ordena registros legados para que o mais recente prevaleça no OneToOne."""
    ordered = list(items or [])
    ordered.sort(
        key=lambda item: (
            _parse_legacy_datetime(item.get("updated_at"))
            or _parse_legacy_datetime(item.get("created_at"))
            or timezone.now()
        )
    )
    return ordered


class ImportReport:
    """Resultado da importação de dados legados."""

    def __init__(self) -> None:
        self.created: list[ServiceApplication] = []
        self.errors: list[str] = []
        self.missing_files: list[str] = []
        self.warnings: list[str] = []

    @property
    def created_count(self) -> int:
        return len(self.created)


class LegacyImporter:
    """Importa inscrições legadas preservando o máximo de informação."""

    def __init__(
        self,
        attachments_root: str | None = None,
        *,
        update_existing: bool = False,
    ) -> None:
        self.attachments_root = attachments_root
        self.update_existing = update_existing
        self._warned_no_storage = False

    def load_records_from_file(self, path: str) -> list[dict[str, Any]]:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict) and "records" in payload:
            return payload["records"]
        return payload

    def import_records(self, records: list[dict[str, Any]]) -> ImportReport:
        report = ImportReport()
        for raw in records:
            try:
                self._import_record(raw, report)
            except Exception as exc:  # noqa: BLE001 - captura e reporta por registro
                report.errors.append(f"{raw.get('protocol', '?')}: {exc}")
        return report

    def _import_record(self, raw: dict[str, Any], report: ImportReport) -> None:
        protocol = str(raw.get("protocol") or "").strip()
        if not protocol:
            raise ValueError("protocolo ausente")

        application = ServiceApplication.all_objects.filter(protocol=protocol).first()
        created = application is None
        if application is not None and not self.update_existing:
            raise ValueError("protocolo duplicado")  # TS-IMP-007
        if application is None:
            application = ServiceApplication(protocol=protocol)

        self._apply_fields(application, raw, created=created)
        self._apply_dates(application, raw)
        self._import_catalog(application, raw.get("catalog_options"))
        self._import_payments(application, raw.get("payments"))
        self._import_triages(application, raw.get("triages"), report)
        self._import_consultations(
            application, raw.get("consultation_meetings"), report
        )
        self._import_events(application, raw.get("events"))
        self._import_attachments(application, raw.get("attachments"), report)
        self._import_deposit_receipts(
            application, raw.get("deposit_receipts"), report
        )
        self._refresh_payment_state(application)
        report.created.append(application)

    # ------------------------------------------------------------------
    # Inscrição
    # ------------------------------------------------------------------

    def _apply_fields(
        self,
        application: ServiceApplication,
        raw: dict[str, Any],
        *,
        created: bool,
    ) -> None:
        application.term = self._resolve_term(raw.get("term"))
        application.modality = raw.get(
            "modality", ServiceApplication.Modality.PROJECT
        )
        application.lifecycle_status = raw.get(
            "lifecycle_status", ServiceApplication.LifecycleStatus.SUBMITTED
        )
        application.researcher_name = raw.get("researcher_name", "")
        application.contact_email = raw.get("contact_email", "")
        application.contact_phone = raw.get("contact_phone")
        application.tax_id = raw.get("tax_id")
        application.institution_name = raw.get("institution_name")
        application.course_name = raw.get("course_name")
        application.mentor_name = raw.get("mentor_name")
        application.project_title = raw.get("project_title")
        application.context_summary = raw.get("context_summary")
        application.general_objectives = raw.get("general_objectives")
        application.variables_and_measurements = raw.get(
            "variables_and_measurements"
        )
        application.contextual_factors = raw.get("contextual_factors")
        application.sampling_and_limitations = raw.get(
            "sampling_and_limitations"
        )
        application.data_management_plan = raw.get("data_management_plan")
        application.expected_results = raw.get("expected_results")
        application.expected_support = raw.get("expected_support")
        application.data_already_collected = raw.get("data_already_collected")
        application.has_whatsapp = bool(raw.get("has_whatsapp"))
        application.wants_refund_receipt = bool(raw.get("wants_refund_receipt"))
        application.refund_receipt_details = raw.get("refund_receipt_details")
        application.refund_account_holder_name = raw.get(
            "refund_account_holder_name"
        )
        application.refund_account_holder_tax_id = raw.get(
            "refund_account_holder_tax_id"
        )
        application.refund_bank_name = raw.get("refund_bank_name")
        application.refund_branch_number = raw.get("refund_branch_number")
        application.refund_bank_account_number = raw.get(
            "refund_bank_account_number"
        )
        application.refund_bank_account_type = raw.get(
            "refund_bank_account_type"
        )
        application.transfer_pending = bool(raw.get("transfer_pending"))
        application.legacy_contact_email = raw.get(
            "legacy_contact_email", raw.get("contact_email")
        )
        application.legacy_contact_tax_id = raw.get(
            "legacy_contact_tax_id", raw.get("tax_id")
        )
        if created:
            application.owner = None
            application.origin = ServiceApplication.Origin.IMPORTED
            application.dataset_audit_required = False  # TS-IMP-005
            application.dataset_audit_state = None
        application.save()

    def _apply_dates(
        self, application: ServiceApplication, raw: dict[str, Any]
    ) -> None:
        updates: dict[str, Any] = {
            "soft_deleted_at": _parse_legacy_datetime(raw.get("soft_deleted_at"))
        }
        created_at = _parse_legacy_datetime(raw.get("created_at"))
        updated_at = _parse_legacy_datetime(raw.get("updated_at"))
        if created_at is not None:
            updates["created_at"] = created_at
        if updated_at is not None:
            updates["updated_at"] = updated_at
        ServiceApplication.all_objects.filter(pk=application.pk).update(**updates)
        application.refresh_from_db()

    def _resolve_term(self, value: Any) -> AcademicTerm:
        if isinstance(value, int):
            return AcademicTerm.objects.get(pk=value)
        if isinstance(value, dict):
            term = AcademicTerm.objects.filter(
                year=value["year"], period=value["period"]
            ).first()
            date_fields = (
                "teaching_start_date",
                "teaching_end_date",
                "submission_start_date",
                "submission_end_date",
            )
            if term is None:
                return AcademicTerm.objects.create(
                    year=value["year"],
                    period=value["period"],
                    **{
                        field: _parse_legacy_date(value.get(field))
                        for field in date_fields
                        if value.get(field)
                    },
                )
            changed = False
            for field in date_fields:
                parsed = _parse_legacy_date(value.get(field))
                if parsed is not None and getattr(term, field) != parsed:
                    setattr(term, field, parsed)
                    changed = True
            if changed:
                term.save(update_fields=[*date_fields, "updated_at"])
            return term
        term = AcademicTerm.current()
        if term is None:
            raise ValueError("período letivo não encontrado para a importação")
        return term

    # ------------------------------------------------------------------
    # Catálogo
    # ------------------------------------------------------------------

    def _import_catalog(
        self, application: ServiceApplication, selections: Any
    ) -> None:
        if self.update_existing:
            application.catalog_selections.all().delete()
        if not selections:
            return
        for item in selections:
            option = CatalogOption.objects.filter(
                category=item.get("category"), code=item.get("code")
            ).first()
            if option is None:
                continue
            ApplicationCatalogSelection.objects.update_or_create(
                application=application,
                option=option,
                defaults={"other_text": item.get("other_text")},
            )

    # ------------------------------------------------------------------
    # Pagamentos
    # ------------------------------------------------------------------

    def _import_payments(
        self, application: ServiceApplication, payments: Any
    ) -> None:
        if self.update_existing:
            PaymentInstrument.objects.filter(
                fee_requirement__application=application
            ).delete()
            FeeRequirement.objects.filter(application=application).delete()
        if not payments:
            return

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in payments:
            fee_type = item.get("fee_type", FeeRequirement.FeeType.APPLICATION_FEE)
            grouped.setdefault(fee_type, []).append(item)

        for fee_type, items in grouped.items():
            representative = next(
                (
                    item
                    for item in items
                    if STATE_TO_INSTRUMENT.get(item.get("state", "paid"))
                    in (
                        PaymentInstrument.State.PAID,
                        PaymentInstrument.State.MANUAL_CONFIRMED,
                    )
                ),
                items[-1],
            )
            document_amount = _decimal(
                representative.get("document_amount") or representative.get("amount")
            )
            discount_amount = _decimal(representative.get("discount_amount"))
            fee = FeeRequirement.objects.create(
                application=application,
                fee_type=fee_type,
                base_amount=document_amount,
                adjustment_amount=-discount_amount,
                amount=document_amount - discount_amount,
                reason=str(representative.get("reason") or "Taxa importada"),
            )
            fee_dates = self._aggregate_dates(items)
            if fee_dates:
                FeeRequirement.objects.filter(pk=fee.pk).update(**fee_dates)

            for item in items:
                state = STATE_TO_INSTRUMENT.get(
                    item.get("state", "paid"), PaymentInstrument.State.CREATED
                )
                instrument_amount = _decimal(
                    item.get("document_amount") or item.get("amount")
                )
                paid_at = _parse_legacy_datetime(item.get("paid_at"))
                instrument = PaymentInstrument.objects.create(
                    fee_requirement=fee,
                    method=item.get(
                        "method", PaymentInstrument.Method.BANK_SLIP
                    ),
                    state=state,
                    amount=instrument_amount,
                    paid_at=paid_at,
                )
                dates = self._dates_from_items([item])
                if dates:
                    PaymentInstrument.objects.filter(pk=instrument.pk).update(
                        **dates
                    )
                self._import_bank_slip(instrument, item)

    def _import_bank_slip(
        self, instrument: PaymentInstrument, item: dict[str, Any]
    ) -> None:
        data = item.get("bank_slip")
        if not data:
            return
        reference = str(data.get("reference") or "").strip()[:60]
        if not reference:
            reference = f"legacy-{data.get('id') or instrument.pk}"[:60]
        if BankSlipPaymentInstrument.objects.filter(
            bank_slip_reference=reference
        ).exists():
            reference = f"{reference[:50]}-{data.get('id') or instrument.pk}"[:60]
        slip = BankSlipPaymentInstrument.objects.create(
            payment_instrument=instrument,
            bank_slip_reference=reference,
            due_date=_parse_legacy_date(data.get("due_date")),
            bank_status=str(data.get("bank_status") or "E")[:1],
            document_amount=_decimal(data.get("document_amount")),
            discount_amount=_decimal(data.get("discount_amount")),
            paid_amount=_decimal(data.get("paid_amount")),
            payment_date=_parse_legacy_date(data.get("payment_date")),
        )
        dates = self._dates_from_items([data])
        if dates:
            BankSlipPaymentInstrument.objects.filter(pk=slip.pk).update(**dates)
        if data.get("manual_confirmed"):
            confirmed_at = _parse_legacy_datetime(
                data.get("manual_confirmed_at")
            ) or _parse_legacy_datetime(data.get("payment_date")) or timezone.now()
            ManualPaymentConfirmation.objects.update_or_create(
                payment_instrument=instrument,
                defaults={
                    "confirmed_at": confirmed_at,
                    "note": data.get("manual_confirmed_by"),
                },
            )

    @staticmethod
    def _dates_from_items(items: list[dict[str, Any]]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        created = [_parse_legacy_datetime(item.get("created_at")) for item in items]
        updated = [_parse_legacy_datetime(item.get("updated_at")) for item in items]
        created_dates = [value for value in created if value is not None]
        updated_dates = [value for value in updated if value is not None]
        if created_dates:
            updates["created_at"] = min(created_dates)
        if updated_dates:
            updates["updated_at"] = max(updated_dates)
        return updates

    def _aggregate_dates(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return self._dates_from_items(items)

    def _refresh_payment_state(self, application: ServiceApplication) -> None:
        fees = list(application.fee_requirements.all())
        non_waived = [fee for fee in fees if not fee.is_waived]
        if not non_waived:
            state = None
        elif all(fee.is_paid for fee in non_waived):
            state = ServiceApplication.PaymentState.PAID
        elif any(fee.is_paid for fee in non_waived):
            state = ServiceApplication.PaymentState.PARTIALLY_PAID
        else:
            state = ServiceApplication.PaymentState.PENDING
        if application.payment_state != state:
            application.payment_state = state
            application.save(update_fields=["payment_state", "updated_at"])

    # ------------------------------------------------------------------
    # Triagens e reuniões
    # ------------------------------------------------------------------

    def _import_triages(
        self,
        application: ServiceApplication,
        triages: Any,
        report: ImportReport,
    ) -> None:
        for item in _chronological(triages):
            scheduled_date = _parse_legacy_date(item.get("scheduled_date"))
            scheduled_time = _parse_legacy_time(item.get("scheduled_time"))
            if scheduled_date is None or scheduled_time is None:
                report.warnings.append(
                    f"{application.protocol}: triagem sem data/hora válida ignorada"
                )
                continue
            screening, _ = ProjectScreening.objects.update_or_create(
                application=application,
                defaults={
                    "scheduled_date": scheduled_date,
                    "scheduled_time": scheduled_time,
                    "meeting_mode": item.get("meeting_mode", "online"),
                    "virtual_link": item.get("virtual_link"),
                    "place": item.get("place"),
                    "decision": item.get("decision"),
                    "decision_note": item.get("decision_note"),
                    "teacher_feedback": item.get("teacher_feedback"),
                    "state": item.get("state", "scheduled"),
                },
            )
            dates = self._dates_from_items([item])
            if dates:
                ProjectScreening.objects.filter(pk=screening.pk).update(**dates)

    def _import_consultations(
        self,
        application: ServiceApplication,
        meetings: Any,
        report: ImportReport,
    ) -> None:
        for item in _chronological(meetings):
            scheduled_date = _parse_legacy_date(item.get("scheduled_date"))
            scheduled_time = _parse_legacy_time(item.get("scheduled_time"))
            if scheduled_date is None or scheduled_time is None:
                report.warnings.append(
                    f"{application.protocol}: reunião sem data/hora válida ignorada"
                )
                continue
            meeting, _ = ConsultationMeeting.objects.update_or_create(
                application=application,
                defaults={
                    "scheduled_date": scheduled_date,
                    "scheduled_time": scheduled_time,
                    "meeting_mode": item.get("meeting_mode", "online"),
                    "virtual_link": item.get("virtual_link"),
                    "place": item.get("place"),
                    "decision": item.get("decision"),
                    "decision_note": item.get("decision_note"),
                    "teacher_feedback": item.get("teacher_feedback"),
                    "state": item.get("state", "scheduled"),
                },
            )
            dates = self._dates_from_items([item])
            if dates:
                ConsultationMeeting.objects.filter(pk=meeting.pk).update(**dates)

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def _import_events(
        self, application: ServiceApplication, events: Any
    ) -> None:
        if self.update_existing:
            ApplicationEvent.objects.filter(
                application=application, event_code__startswith="legacy."
            ).delete()
        for item in events or []:
            event = ApplicationEvent.objects.create(
                application=application,
                event_code=str(item.get("event_code") or "legacy.evento")[:100],
                description=item.get("description"),
                metadata=item.get("metadata"),
            )
            occurred_at = _parse_legacy_datetime(item.get("occurred_at"))
            if occurred_at is not None:
                ApplicationEvent.objects.filter(pk=event.pk).update(
                    occurred_at=occurred_at, created_at=occurred_at
                )

    # ------------------------------------------------------------------
    # Arquivos
    # ------------------------------------------------------------------

    def _import_attachments(
        self,
        application: ServiceApplication,
        attachments: Any,
        report: ImportReport,
    ) -> None:
        if not attachments:
            return
        if self.attachments_root is None:
            self._warn_no_storage(report)
            return
        if self.update_existing:
            application.attachments.all().delete()
            FileAsset.objects.filter(
                application=application,
                purpose=FileAsset.Purpose.APPLICATION_ATTACHMENT,
            ).delete()
        for item in attachments:
            file_asset = self._create_file_asset(
                application,
                item,
                FileAsset.Purpose.APPLICATION_ATTACHMENT,
                report,
            )
            if file_asset is not None:
                application.attachments.create(file_asset=file_asset)

    def _import_deposit_receipts(
        self,
        application: ServiceApplication,
        receipts: Any,
        report: ImportReport,
    ) -> None:
        if not receipts:
            return
        if self.attachments_root is None:
            self._warn_no_storage(report)
            return
        if self.update_existing:
            FileAsset.objects.filter(
                application=application,
                purpose=FileAsset.Purpose.PAYMENT_RECEIPT,
            ).delete()
        for item in receipts:
            self._create_file_asset(
                application,
                item,
                FileAsset.Purpose.PAYMENT_RECEIPT,
                report,
            )

    def _create_file_asset(
        self,
        application: ServiceApplication,
        item: dict[str, Any],
        purpose: str,
        report: ImportReport,
    ) -> FileAsset | None:
        legacy_path = item.get("legacy_path")
        if not legacy_path:
            report.missing_files.append("?")
            return None
        assert self.attachments_root is not None
        full_path = (
            os.path.join(self.attachments_root, legacy_path)
            if not os.path.isabs(legacy_path)
            else legacy_path
        )
        if not os.path.exists(full_path):
            report.missing_files.append(str(legacy_path))  # TS-IMP-008
            return None
        with open(full_path, "rb") as handle:
            content = handle.read()
        original_filename = item.get("original_filename") or os.path.basename(
            str(legacy_path)
        )
        content_type = (
            item.get("content_type")
            or mimetypes.guess_type(original_filename)[0]
            or "application/octet-stream"
        )
        file_asset = create_file_asset_from_bytes(
            application=application,
            uploaded_by=None,
            content=content,
            filename=original_filename,
            content_type=content_type,
            purpose=purpose,  # TS-IMP-003
        )
        FileAsset.objects.filter(pk=file_asset.pk).update(
            original_filename=str(original_filename)[:255]
        )
        created_at = _parse_legacy_datetime(item.get("created_at"))
        if created_at is not None:
            FileAsset.objects.filter(pk=file_asset.pk).update(
                created_at=created_at, updated_at=created_at
            )
        return file_asset

    def _warn_no_storage(self, report: ImportReport) -> None:
        if self._warned_no_storage:
            return
        self._warned_no_storage = True
        report.warnings.append(
            "Pasta de storage não informada: anexos e comprovantes foram ignorados."
        )
