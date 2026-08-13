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
        attachments: list[dict[str, Any]] | None = None,
        context_overrides: dict[str, Any] | None = None,
        bcc: list[str] | None = None,
    ) -> None:
        merged_context = {**context_data, **(context_overrides or {})}
        send_notification_task.delay(
            template_code=template_code,
            recipient_email=recipient_email,
            context_data=merged_context,
            application_id=application_id,
            attachments=attachments,
            bcc=bcc,
        )

    def notify_application_submitted(
        self,
        application: ServiceApplication,
        boleto_failed: bool = False,
    ) -> None:
        """Notifica o candidato (e a equipe CEA) sobre a submissão (TS-NOT-001).

        ``boleto_failed`` ativa o aviso de instabilidade no e-mail do candidato
        (paridade com o ``NotifyInscribedAboutApplication`` do legado): quando a
        integração SOAP de boletos falha durante a emissão, o candidato recebe a
        confirmação de submissão acompanhada de um alerta de que o boleto ainda
        será enviado, evitando pânico e chamados de suporte. Nesse caso apenas o
        candidato é notificado (a equipe CEA já foi alertada via
        ``notify_bank_slip_failure``).
        """
        context = self._base_context(application)
        self._enqueue(
            "application_submitted_candidate",
            application.contact_email,
            context,
            application.pk,
            context_overrides={"boleto_failed": bool(boleto_failed)},
        )
        if boleto_failed:
            return
        self._enqueue(
            "application_submitted_center",
            self.center_email,
            context,
            application.pk,
            attachments=self._application_submitted_center_attachments(application),
        )

    def _application_submitted_center_attachments(
        self, application: ServiceApplication
    ) -> list[dict[str, Any]]:
        """Monta os anexos do e-mail do CEA: ficha em PDF + arquivos do candidato.

        Paridade com os Mailables ``NotifyCEAAboutApplication`` e
        ``NotifyInscribedAboutApplication`` do legado (Gap A): gera a ficha de
        inscrição via ``DocumentRenderingService`` e anexa todos os ``FileAsset``
        de ``application_attachment`` enviados pelo candidato.
        """
        from django.core.files.storage import default_storage

        from documents.services import DocumentRenderingService
        from files.models import FileAsset

        attachments: list[dict[str, Any]] = []
        try:
            pdf = DocumentRenderingService().render_application_full_pdf(application)
            attachments.append(
                {
                    "filename": f"ficha-{application.protocol}.pdf",
                    "content": pdf,
                    "mimetype": "application/pdf",
                }
            )
        except Exception:  # noqa: BLE001 - falha de renderização não impede o envio
            pass
        for asset in (
            application.file_assets.filter(
                purpose=FileAsset.Purpose.APPLICATION_ATTACHMENT
            )
            .order_by("created_at")
            .iterator()
        ):
            try:
                content = default_storage.open(asset.storage_key, "rb").read()
            except FileNotFoundError:
                continue
            attachments.append(
                {
                    "filename": asset.original_filename,
                    "content": content,
                    "mimetype": asset.content_type or "application/octet-stream",
                }
            )
        return attachments

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

    def notify_modality_changed(
        self,
        application: ServiceApplication,
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        """Notifica o candidato sobre mudança de modalidade pela secretaria.

        Equivale ao Mailable ``NotifyServiceChange`` do sistema legado (TS-NOT-011):
        quando a secretaria altera a modalidade, o candidato deve ser informado da
        nova dívida/condição via e-mail. ``attachments`` carrega o PDF do novo
        boleto (paridade com o ``attachData()`` do legado, Gap B).
        """
        context = self._base_context(application)
        context["new_modality"] = application.get_modality_display()
        self._enqueue(
            "service_modality_changed",
            application.contact_email,
            context,
            application.pk,
            attachments=attachments,
        )

    def notify_bank_slip_regenerated(
        self,
        application: ServiceApplication,
        template_code: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        """Notifica o candidato sobre um boleto reemitido.

        ``template_code`` diferencia a regeneração automática (cron/Worker,
        ``payment_failure_regenerated``) da regeneração manual pela secretaria
        (``payment_slip_regenerated``), em paridade com o legado.

        ``attachments`` carrega o PDF do boleto (paridade com o Mailable
        ``NotifyUserNewBoleto`` que usava ``attachData()``).
        """
        context = self._base_context(application)
        # Paridade com o ``RegenerateAndNotifyPaymentFailure`` do legado: ao
        # reemitir o boleto automaticamente, a equipe CEA recebe a cópia oculta
        # (``$mail->bcc(env('MAIL_CEA'))``) para manter visibilidade das
        # reemissões automáticas.
        self._enqueue(
            template_code,
            application.contact_email,
            context,
            application.pk,
            attachments=attachments,
            bcc=[self.center_email],
        )

    def notify_overdue_reminder(self, application: ServiceApplication) -> None:
        """Envia cobrança de boleto vencido ao candidato.

        Equivale ao Mailable ``NotifyOverdueBankSlip`` do sistema legado
        (``ApplicationController@sendOverdueReminders``).
        """
        context = self._base_context(application)
        self._enqueue(
            "overdue_payment_reminder",
            application.contact_email,
            context,
            application.pk,
        )

    def notify_bank_slip_failure(
        self, application: ServiceApplication, error_message: str
    ) -> None:
        """Alerta a equipe CEA sobre falha na integração SOAP de boletos.

        Equivale ao Mailable ``NotifyCEABoletoFailure`` do sistema legado: quando
        o serviço de boletos está indisponível, o candidato fica sem o boleto e a
        secretaria precisa ser notificada proativamente (paridade com o Laravel).
        """
        context = self._base_context(application)
        context["error_message"] = error_message
        self._enqueue(
            "bank_slip_generation_failure",
            self.center_email,
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
