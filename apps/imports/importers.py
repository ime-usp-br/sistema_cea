import json
import os
from decimal import Decimal
from typing import Any

from applications.models import ServiceApplication
from files.models import FileAsset
from files.services import create_file_asset_from_bytes
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm

STATE_TO_INSTRUMENT = {
    "paid": PaymentInstrument.State.PAID,
    "manual_confirmed": PaymentInstrument.State.MANUAL_CONFIRMED,
    "canceled": PaymentInstrument.State.CANCELED,
    "superseded": PaymentInstrument.State.SUPERSEDED,
    "expired": PaymentInstrument.State.EXPIRED,
}


class ImportReport:
    """Resultado da importação de dados legados."""

    def __init__(self) -> None:
        self.created: list[ServiceApplication] = []
        self.errors: list[str] = []
        self.missing_files: list[str] = []

    @property
    def created_count(self) -> int:
        return len(self.created)


class LegacyImporter:
    """Importa inscrições legadas preservando contatos, pagamentos e anexos."""

    def __init__(self, attachments_root: str | None = None) -> None:
        self.attachments_root = attachments_root

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
        if ServiceApplication.all_objects.filter(protocol=protocol).exists():
            raise ValueError("protocolo duplicado")  # TS-IMP-007

        term = self._resolve_term(raw.get("term"))
        application = ServiceApplication.objects.create(
            term=term,
            owner=None,
            protocol=protocol,
            modality=raw.get("modality", ServiceApplication.Modality.PROJECT),
            lifecycle_status=raw.get(
                "lifecycle_status", ServiceApplication.LifecycleStatus.SUBMITTED
            ),
            payment_state=raw.get("payment_state"),
            dataset_audit_required=False,  # TS-IMP-005
            dataset_audit_state=None,
            origin=ServiceApplication.Origin.IMPORTED,  # TS-IMP-001
            researcher_name=raw.get("researcher_name", ""),
            contact_email=raw.get("contact_email", ""),
            contact_phone=raw.get("contact_phone"),
            tax_id=raw.get("tax_id"),
            project_title=raw.get("project_title"),
            legacy_contact_email=raw.get(
                "legacy_contact_email", raw.get("contact_email")
            ),  # TS-IMP-001
            legacy_contact_tax_id=raw.get(
                "legacy_contact_tax_id", raw.get("tax_id")
            ),  # TS-IMP-001
        )
        self._import_payments(application, raw.get("payments"))
        self._import_attachments(application, raw.get("attachments"), report)
        report.created.append(application)

    def _resolve_term(self, value: Any) -> AcademicTerm:
        if isinstance(value, int):
            return AcademicTerm.objects.get(pk=value)
        if isinstance(value, dict):
            term = AcademicTerm.objects.filter(
                year=value["year"], period=value["period"]
            ).first()
            if term is None:
                term = AcademicTerm.objects.create(
                    year=value["year"], period=value["period"]
                )
            return term
        return AcademicTerm.objects.first()  # type: ignore[return-value]

    def _import_payments(self, application: ServiceApplication, payments: Any) -> None:
        if not payments:
            return
        for item in payments:
            amount = Decimal(str(item.get("amount") or "0"))
            fee = FeeRequirement.objects.create(
                application=application,
                fee_type=item.get(
                    "fee_type", FeeRequirement.FeeType.APPLICATION_FEE
                ),
                base_amount=amount,
                adjustment_amount=Decimal("0.00"),
                amount=amount,
                reason=item.get("reason", "Taxa importada"),
            )
            state_raw = item.get("state", "paid")
            state = STATE_TO_INSTRUMENT.get(state_raw, PaymentInstrument.State.PAID)
            instrument = PaymentInstrument.objects.create(
                fee_requirement=fee,
                method=item.get("method", PaymentInstrument.Method.BANK_SLIP),
                state=state,
                amount=amount,
                paid_at=item.get("paid_at"),
            )
            if state in (
                PaymentInstrument.State.PAID,
                PaymentInstrument.State.MANUAL_CONFIRMED,
            ):
                application.payment_state = ServiceApplication.PaymentState.PAID
                application.save(update_fields=["payment_state", "updated_at"])
            instrument.save()

    def _import_attachments(
        self,
        application: ServiceApplication,
        attachments: Any,
        report: ImportReport,
    ) -> None:
        if not attachments:
            return
        for item in attachments:
            legacy_path = item.get("legacy_path")
            if not legacy_path or self.attachments_root is None:
                report.missing_files.append(str(legacy_path or "?"))
                continue
            full_path = (
                os.path.join(self.attachments_root, legacy_path)
                if not os.path.isabs(legacy_path)
                else legacy_path
            )
            if not os.path.exists(full_path):
                report.missing_files.append(legacy_path)  # TS-IMP-008
                continue
            with open(full_path, "rb") as handle:
                content = handle.read()
            file_asset = create_file_asset_from_bytes(
                application=application,
                uploaded_by=None,
                content=content,
                filename=os.path.basename(legacy_path),
                content_type=item.get("content_type", "application/octet-stream"),
                purpose=FileAsset.Purpose.APPLICATION_ATTACHMENT,  # TS-IMP-003
            )
            application.attachments.create(file_asset=file_asset)
