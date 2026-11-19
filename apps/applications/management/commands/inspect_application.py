"""Inspeciona o estado completo de uma inscrição para asserções E2E.

Emite JSON com lifecycle, taxas, instrumentos, auditoria, agendamentos,
reembolsos e a trilha de eventos. É somente leitura e usado pelos testes de
navegador para verificar efeitos que não aparecem integralmente na tela.
"""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Emite o estado completo de uma inscrição em JSON (E2E)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--protocol", required=True, help="Protocolo da inscrição.")
        parser.add_argument(
            "--json",
            action="store_true",
            help="Mantido por compatibilidade; a saída é sempre JSON.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from applications.models import ServiceApplication

        application = (
            ServiceApplication.all_objects.select_related(
                "term", "owner", "project_screening", "consultation_meeting"
            )
            .filter(protocol=options["protocol"])
            .first()
        )
        if application is None:
            raise CommandError(f"Inscrição {options['protocol']} não encontrada.")

        fees = []
        for fee in application.fee_requirements.all().order_by("created_at"):
            instruments = []
            for instrument in fee.payment_instruments.all():
                item: dict[str, Any] = {
                    "id": instrument.pk,
                    "method": instrument.method,
                    "state": instrument.state,
                    "amount": str(instrument.amount),
                    "paid_at": (
                        instrument.paid_at.isoformat() if instrument.paid_at else None
                    ),
                }
                pix = getattr(instrument, "pix_instrument", None)
                if pix is not None:
                    item["pix_reference"] = pix.pix_reference
                    item["pix_status"] = pix.external_status
                slip = getattr(instrument, "bank_slip_instrument", None)
                if slip is not None:
                    item["bank_slip_reference"] = slip.bank_slip_reference
                    item["bank_status"] = slip.bank_status
                    item["due_date"] = (
                        slip.due_date.isoformat() if slip.due_date else None
                    )
                instruments.append(item)
            fees.append(
                {
                    "id": fee.pk,
                    "type": fee.fee_type,
                    "amount": str(fee.amount),
                    "is_paid": fee.is_paid,
                    "is_waived": fee.is_waived,
                    "paid_amount": str(fee.paid_amount),
                    "instruments": instruments,
                }
            )

        submissions = []
        for submission in application.audit_submissions.all().order_by("submitted_at"):
            submissions.append(
                {
                    "id": submission.pk,
                    "state": submission.state,
                    "channel": submission.submission_channel,
                    "has_file": submission.file_asset_id is not None,
                    "external_url": submission.external_url,
                    "reviews": [
                        {
                            "outcome": review.outcome,
                            "note": review.note,
                            "reviewer": review.reviewer_id,
                        }
                        for review in submission.reviews.all()
                    ],
                    "resolutions": [
                        {
                            "resolution": resolution.resolution,
                            "note": resolution.note,
                            "target_term": resolution.target_term_id,
                        }
                        for resolution in submission.resolutions.all()
                    ],
                }
            )

        screening = getattr(application, "project_screening", None)
        meeting = getattr(application, "consultation_meeting", None)
        events = [
            {
                "code": event.event_code,
                "actor": event.actor_id,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in application.events.all().order_by("occurred_at")
        ]
        refunds = [
            {
                "id": refund.pk,
                "status": refund.status,
                "amount": str(refund.amount),
            }
            for refund in application.refund_requests.all()
        ]

        self.stdout.write(
            json.dumps(
                {
                    "protocol": application.protocol,
                    "lifecycle_status": application.lifecycle_status,
                    "payment_state": application.payment_state,
                    "modality": application.modality,
                    "term": {
                        "id": application.term_id,
                        "year": application.term.year,
                        "period": application.term.period,
                    },
                    "owner": application.owner.username if application.owner else None,
                    "soft_deleted": application.soft_deleted_at is not None,
                    "transfer_pending": application.transfer_pending,
                    "dataset_audit_state": application.dataset_audit_state,
                    "fees": fees,
                    "audit_submissions": submissions,
                    "screening": (
                        {
                            "id": screening.pk,
                            "state": screening.state,
                            "decision": screening.decision,
                            "teacher_feedback": screening.teacher_feedback,
                        }
                        if screening is not None
                        else None
                    ),
                    "consultation": (
                        {
                            "id": meeting.pk,
                            "state": meeting.state,
                            "decision": meeting.decision,
                            "teacher_feedback": meeting.teacher_feedback,
                        }
                        if meeting is not None
                        else None
                    ),
                    "refunds": refunds,
                    "events": events,
                },
                ensure_ascii=False,
            )
        )
