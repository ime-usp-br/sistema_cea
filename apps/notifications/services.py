from typing import Any

from django.conf import settings

from applications.models import ServiceApplication
from meetings.models import ProjectScreening
from payments.models import PaymentInstrument

from .tasks import send_notification_task


class NotificationService:
    """Enfileira despachos assíncronos de notificações por e-mail."""

    def __init__(self) -> None:
        self.center_email = settings.NOTIFICATION_CENTER_EMAIL

    @staticmethod
    def _enqueue(
        template_code: str,
        recipient_email: str,
        context_data: dict[str, Any],
        application_id: int | None = None,
    ) -> None:
        send_notification_task.delay(
            template_code=template_code,
            recipient_email=recipient_email,
            context_data=context_data,
            application_id=application_id,
        )

    def notify_application_submitted(self, application: ServiceApplication) -> None:
        """Notifica o candidato (e a equipe CEA) sobre a submissão (TS-NOT-001)."""
        context = self._base_context(application)
        self._enqueue(
            "application_submitted_candidate",
            application.contact_email,
            context,
            application.pk,
        )
        self._enqueue(
            "application_submitted_center",
            self.center_email,
            context,
            application.pk,
        )

    def notify_correction_requested(
        self, application: ServiceApplication, note: str | None = None
    ) -> None:
        """Notifica o candidato sobre correção solicitada (TS-NOT-002)."""
        context = self._base_context(application)
        context["note"] = note or ""
        self._enqueue(
            "dataset_correction_requested",
            application.contact_email,
            context,
            application.pk,
        )

    def notify_dataset_approved(self, application: ServiceApplication) -> None:
        """Notifica o candidato sobre aprovação da auditoria (TS-NOT-003)."""
        context = self._base_context(application)
        self._enqueue(
            "dataset_approved",
            application.contact_email,
            context,
            application.pk,
        )

    def notify_dataset_rejected(
        self, application: ServiceApplication, note: str | None = None
    ) -> None:
        """Notifica o candidato sobre rejeição da auditoria (TS-NOT-004)."""
        context = self._base_context(application)
        context["note"] = note or ""
        self._enqueue(
            "dataset_rejected",
            application.contact_email,
            context,
            application.pk,
        )
        self._enqueue(
            "dataset_rejected_secretariat",
            self.center_email,
            context,
            application.pk,
        )

    def notify_payment_created(
        self, application: ServiceApplication, instrument: PaymentInstrument
    ) -> None:
        """Notifica o candidato sobre a cobrança criada (TS-NOT-005)."""
        context = self._base_context(application)
        context["instrument_id"] = instrument.pk
        context["method"] = instrument.method
        context["amount"] = str(instrument.amount)
        self._enqueue(
            "payment_created",
            application.contact_email,
            context,
            application.pk,
        )

    def notify_payment_confirmed(
        self, application: ServiceApplication, instrument: PaymentInstrument
    ) -> None:
        """Notifica o candidato sobre pagamento confirmado (TS-NOT-006/007)."""
        context = self._base_context(application)
        context["instrument_id"] = instrument.pk
        context["method"] = instrument.method
        context["amount"] = str(instrument.amount)
        self._enqueue(
            "payment_confirmed",
            application.contact_email,
            context,
            application.pk,
        )

    def notify_screening_scheduled(
        self, application: ServiceApplication, screening: ProjectScreening
    ) -> None:
        """Notifica o candidato sobre o agendamento da triagem."""
        context = self._base_context(application)
        context["screening_id"] = screening.pk
        context["scheduled_date"] = str(screening.scheduled_date)
        context["scheduled_time"] = str(screening.scheduled_time)
        context["meeting_mode"] = screening.meeting_mode
        context["virtual_link"] = screening.virtual_link or ""
        context["place"] = screening.place or ""
        self._enqueue(
            "screening_scheduled",
            application.contact_email,
            context,
            application.pk,
        )

    @staticmethod
    def _base_context(application: ServiceApplication) -> dict[str, Any]:
        return {
            "protocol": application.protocol,
            "candidate_name": application.researcher_name,
            "modality": application.get_modality_display(),
            "term": str(application.term),
        }
