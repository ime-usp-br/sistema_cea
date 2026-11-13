import contextlib
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from applications.models import ApplicationEvent, ServiceApplication

from .models import (
    FeeRequirement,
    ManualPaymentConfirmation,
    PaymentInstrument,
    RefundRequest,
)

APPLICATION_FEE_PROJECT = Decimal("80.00")
APPLICATION_FEE_CONSULTATION = Decimal("140.00")
PROJECT_FEE = Decimal("250.00")
SUPPLEMENT_FEE = Decimal("60.00")
CONSULTATION_TO_PROJECT_CREDIT = Decimal("60.00")


class PaymentDomainError(ValueError):
    """Erro de domínio para o módulo financeiro."""


def fee_status_label(fee: FeeRequirement) -> str:
    """Rótulo de situação da taxa no vocabulário do legado.

    Reutilizado na lista de inscrições, nas filas de triagem/reunião e no
    relatório financeiro: "Pago", "Emitido", "Cancelado", "Não Emitido",
    "Dispensada".
    """
    instruments = list(fee.payment_instruments.all())
    if fee.is_waived:
        return "Dispensada"
    if any(
        item.state
        in (PaymentInstrument.State.PAID, PaymentInstrument.State.MANUAL_CONFIRMED)
        for item in instruments
    ):
        return "Pago"
    if any(
        item.state in (PaymentInstrument.State.ACTIVE, PaymentInstrument.State.CREATED)
        for item in instruments
    ):
        return "Emitido"
    if instruments:
        return "Cancelado"
    return "Não Emitido"


def record_application_event(
    *,
    application: ServiceApplication,
    event_code: str,
    actor: Any = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ApplicationEvent:
    """Registra um evento na trilha de auditoria da inscrição."""
    return ApplicationEvent.objects.create(
        application=application,
        event_code=event_code,
        actor=actor,
        description=description,
        metadata=metadata,
    )


def cancel_external_charge(instrument: PaymentInstrument) -> None:
    """Cancela (best-effort) a cobrança externa ativa no gateway.

    Paridade com o legado: quando um instrumento deixa de ser o ativo
    (mudança de modalidade ou confirmação manual de pagamento), a cobrança
    antiga — em especial o boleto registrado — deve ser baixada no banco para
    evitar que o candidato pague em duplicidade (DDA do banco).

    O cancelamento é *best-effort* (``try/except``), seguindo o padrão do
    Laravel ``try { $fee->cancelarBoleto(); } catch (...)``: se o gateway estiver
    indisponível, o fluxo local não deve ser bloqueado. O estado local também é
    atualizado para ``CANCELED`` mantendo a consistência interna. Pix é ignorado
    aqui pois expira por validade no gateway.
    """
    from bank_slips.gateways import BankSlipGateway
    from bank_slips.models import BankSlipPaymentInstrument

    if instrument.method != PaymentInstrument.Method.BANK_SLIP:
        return
    slip = BankSlipPaymentInstrument.objects.filter(
        payment_instrument=instrument
    ).first()
    if slip is None or not slip.bank_slip_reference:
        return
    if instrument.state in (
        PaymentInstrument.State.PAID,
        PaymentInstrument.State.MANUAL_CONFIRMED,
    ):
        return
    with contextlib.suppress(Exception):  # noqa: BLE001 - cancelamento best-effort
        BankSlipGateway().cancelar_boleto(slip.bank_slip_reference)
    if instrument.state != PaymentInstrument.State.CANCELED:
        instrument.state = PaymentInstrument.State.CANCELED
        instrument.active_unique_fee_token = None
        instrument.save(update_fields=["state", "active_unique_fee_token", "updated_at"])
    if slip.bank_status != BankSlipPaymentInstrument.BankStatus.CANCELED:
        slip.bank_status = BankSlipPaymentInstrument.BankStatus.CANCELED
        slip.cancellation_date = timezone.now().date()
        slip.save(update_fields=["bank_status", "cancellation_date", "updated_at"])


def refresh_payment_state(application: ServiceApplication) -> str | None:
    """Recomputa o payment_state da inscrição com base nas taxas pagas."""
    fees = list(application.fee_requirements.all())
    non_waived = [fee for fee in fees if not fee.is_waived]
    unpaid = [fee for fee in non_waived if not fee.is_paid]
    if not non_waived:
        application.payment_state = None
    elif not unpaid:
        application.payment_state = ServiceApplication.PaymentState.PAID
    elif any(fee.is_paid for fee in non_waived):
        application.payment_state = ServiceApplication.PaymentState.PARTIALLY_PAID
    else:
        application.payment_state = ServiceApplication.PaymentState.PENDING
    return application.payment_state


def advance_lifecycle_after_application_fee(application: ServiceApplication) -> None:
    """Avança o fluxo da inscrição após o pagamento de uma taxa (TS-PAY-008).

    Sequência do Projeto (após pagar):
      - pagar a taxa de inscrição (sem taxa de projeto) -> awaiting_dataset_submission
        (auditoria);
      - pagar a taxa de projeto (já criada)            -> approved_as_project.
    Enquanto houver taxa de projeto pendente, a inscrição permanece em
    ``awaiting_payment`` (D3: o candidato paga a taxa de projeto pela UI).

    Consulta: quando não há mais taxas pendentes (ex.: complemento de R$ 60)
    -> awaiting_consultation_scheduling.
    """
    if application.lifecycle_status != ServiceApplication.LifecycleStatus.AWAITING_PAYMENT:
        return
    if application.modality == ServiceApplication.Modality.PROJECT:
        project_fee = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.PROJECT_FEE
        ).first()
        if project_fee is not None and project_fee.is_paid:
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT
            )
        elif project_fee is not None:
            # Taxa de projeto criada e ainda pendente: mantém aguardando pagamento.
            return
        else:
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION
            )
    else:
        pending_fees = [
            fee
            for fee in application.fee_requirements.all()
            if not fee.is_waived and not fee.is_paid
        ]
        if pending_fees:
            return
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
        )


class FeeSelectionService:
    """Seleciona a taxa a pagar na área do candidato (D3).

    Ordem canônica do legado: inscrição → projeto → complemento. Sem taxa
    explícita, devolve a próxima pendente; se todas estiverem pagas, a
    primeira taxa existente (para exibição de status).
    """

    FEE_ORDER: tuple[str, ...] = (
        FeeRequirement.FeeType.APPLICATION_FEE.value,
        FeeRequirement.FeeType.PROJECT_FEE.value,
        FeeRequirement.FeeType.SUPPLEMENT_FEE.value,
    )

    def ordered_fees(self, application: ServiceApplication) -> list[FeeRequirement]:
        fees = list(application.fee_requirements.all())
        return sorted(fees, key=self._sort_key)

    def _sort_key(self, fee: FeeRequirement) -> tuple[int, int]:
        try:
            rank = self.FEE_ORDER.index(fee.fee_type)
        except ValueError:  # pragma: no cover - protegido pela enum do model
            rank = len(self.FEE_ORDER)
        return (rank, fee.pk or 0)

    def select_fee(
        self, application: ServiceApplication, fee_id: int | None = None
    ) -> FeeRequirement | None:
        fees = self.ordered_fees(application)
        if not fees:
            return None
        if fee_id is not None:
            for fee in fees:
                if fee.pk == fee_id:
                    return fee
        for fee in fees:
            if not fee.is_waived and not fee.is_paid:
                return fee
        return fees[0]


class FeeCalculationService:
    """Responsável pela criação e cálculo de taxas."""

    def create_application_fee(
        self,
        application: ServiceApplication,
        *,
        adjustment_reason: str | None = None,
    ) -> FeeRequirement | None:
        existing = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        ).first()
        if existing is not None:
            return None
        if application.modality == ServiceApplication.Modality.PROJECT:
            base = APPLICATION_FEE_PROJECT
        else:
            base = APPLICATION_FEE_CONSULTATION
        return FeeRequirement.objects.create(
            application=application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=base,
            adjustment_amount=Decimal("0.00"),
            amount=base,
            adjustment_reason=adjustment_reason,
            reason="Taxa de inscrição",
        )

    def create_project_fee(
        self,
        application: ServiceApplication,
        *,
        adjustment_reason: str | None = None,
    ) -> FeeRequirement | None:
        existing = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.PROJECT_FEE
        ).first()
        if existing is not None:
            return None
        adjustment = Decimal("0.00")
        credit = application.modality_credit_amount or Decimal("0.00")
        if credit > 0:
            adjustment = -credit
        amount = PROJECT_FEE + adjustment
        return FeeRequirement.objects.create(
            application=application,
            fee_type=FeeRequirement.FeeType.PROJECT_FEE,
            base_amount=PROJECT_FEE,
            adjustment_amount=adjustment,
            amount=amount,
            adjustment_reason=adjustment_reason or (
                "Crédito de modalidade aplicado" if credit > 0 else None
            ),
            reason="Taxa de projeto",
        )

    def create_supplement_fee(
        self,
        application: ServiceApplication,
        amount: Decimal = SUPPLEMENT_FEE,
        *,
        adjustment_reason: str | None = None,
    ) -> FeeRequirement | None:
        existing = application.fee_requirements.filter(
            fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE
        ).first()
        if existing is not None:
            return None
        return FeeRequirement.objects.create(
            application=application,
            fee_type=FeeRequirement.FeeType.SUPPLEMENT_FEE,
            base_amount=amount,
            adjustment_amount=Decimal("0.00"),
            amount=amount,
            adjustment_reason=adjustment_reason,
            reason="Taxa complementar de modalidade",
        )


class PaymentOrchestrationService:
    """Orquestra a criação de instrumentos de pagamento.

    Garante a regra de ouro: apenas UM instrumento ativo por taxa.
    """

    def create_payment_instrument(
        self,
        *,
        fee_requirement: FeeRequirement,
        method: str,
        created_by: Any = None,
    ) -> PaymentInstrument:
        if fee_requirement.is_paid:
            raise PaymentDomainError(
                "A taxa já foi paga e não pode ter novos instrumentos de pagamento."
            )  # TS-PAY-006
        method_enum = PaymentInstrument.Method(method)
        with transaction.atomic():
            # Libera o token de instrumentos não pagos não ativos (TS-PAY-007).
            self._release_stale_tokens(fee_requirement)
            active = fee_requirement.payment_instruments.filter(
                state=PaymentInstrument.State.ACTIVE
            ).first()
            token = active.active_unique_fee_token if active else fee_requirement.pk
            if active is not None:
                # Libera o token antes de criar o novo instrumento (TS-PAY-003/004).
                active.active_unique_fee_token = None
                active.save(update_fields=["active_unique_fee_token", "updated_at"])
            instrument = PaymentInstrument.objects.create(
                fee_requirement=fee_requirement,
                method=method_enum.value,
                state=PaymentInstrument.State.ACTIVE,
                amount=fee_requirement.amount,
                created_by=created_by,
                active_unique_fee_token=token,
            )
            if active is not None:
                active.state = PaymentInstrument.State.SUPERSEDED
                active.superseded_by = instrument
                active.save(update_fields=["state", "superseded_by", "updated_at"])
            record_application_event(
                application=fee_requirement.application,
                event_code="payment.instrument_created",
                actor=created_by,
                description=f"Instrumento {method_enum.value} criado.",
                metadata={"instrument_id": instrument.pk, "method": method_enum.value},
            )
        from notifications.services import NotificationService

        NotificationService().notify_payment_created(
            fee_requirement.application, instrument
        )
        return instrument

    def _release_stale_tokens(self, fee_requirement: FeeRequirement) -> None:
        stale_states = [
            PaymentInstrument.State.EXPIRED,
            PaymentInstrument.State.CANCELED,
            PaymentInstrument.State.SUPERSEDED,
            PaymentInstrument.State.FAILED,
            PaymentInstrument.State.CREATED,
            PaymentInstrument.State.REQUIRES_REVIEW,
        ]
        stale = fee_requirement.payment_instruments.filter(
            state__in=stale_states, active_unique_fee_token__isnull=False
        )
        for item in stale:
            item.active_unique_fee_token = None
            item.save(update_fields=["active_unique_fee_token", "updated_at"])


class ManualPaymentService:
    """Confirmação administrativa de pagamento manual."""

    def confirm_manual_payment(
        self,
        *,
        instrument: PaymentInstrument,
        confirmed_by: Any,
        note: str | None = None,
    ) -> ManualPaymentConfirmation:
        if instrument.state in (
            PaymentInstrument.State.PAID,
            PaymentInstrument.State.MANUAL_CONFIRMED,
        ):
            raise PaymentDomainError(
                "O instrumento já consta como pago e não pode ser confirmado novamente."
            )  # TS-MAN-004
        if instrument.state not in (
            PaymentInstrument.State.CREATED,
            PaymentInstrument.State.ACTIVE,
            PaymentInstrument.State.REQUIRES_REVIEW,
            PaymentInstrument.State.FAILED,
        ):
            raise PaymentDomainError(
                "O instrumento não pode ser confirmado manualmente no estado atual."
            )
        fee = instrument.fee_requirement
        application = fee.application
        now = timezone.now()
        # Paridade com o Laravel (ApplicationController@confirmManualPayment):
        # a secretaria só pode confirmar o depósito de um boleto já vencido
        # (hoje ou no passado). Confirmar antes do vencimento pode gerar
        # conflito de DDA se o aluno pagar no banco no mesmo dia (Gap C).
        from bank_slips.models import BankSlipPaymentInstrument

        slip = BankSlipPaymentInstrument.objects.filter(
            payment_instrument=instrument
        ).first()
        if slip is not None and slip.due_date is not None and slip.due_date > timezone.localdate():
            raise PaymentDomainError("Este boleto ainda não está vencido")
        with transaction.atomic():
            # Paridade com o legado: ao confirmar pagamento manual, boleto/Pix
            # ativo na mesma taxa deve ser baixado no gateway para evitar
            # pagamento em duplicidade (Gap C). Inclui boletos SUPERSEDED, pois
            # continuam válidos no DDA mesmo após a troca de forma de pagamento.
            for slip_instrument in fee.payment_instruments.filter(
                method=PaymentInstrument.Method.BANK_SLIP,
                state__in=[
                    PaymentInstrument.State.ACTIVE,
                    PaymentInstrument.State.CREATED,
                    PaymentInstrument.State.SUPERSEDED,
                    PaymentInstrument.State.FAILED,
                    PaymentInstrument.State.REQUIRES_REVIEW,
                ],
            ).exclude(pk=instrument.pk):
                cancel_external_charge(slip_instrument)
            confirmation = ManualPaymentConfirmation.objects.create(
                payment_instrument=instrument,
                confirmed_by=confirmed_by,
                confirmed_at=now,
                note=note,
            )
            instrument.state = PaymentInstrument.State.MANUAL_CONFIRMED
            instrument.paid_at = now
            instrument.save(update_fields=["state", "paid_at", "updated_at"])
            refresh_payment_state(application)
            advance_lifecycle_after_application_fee(application)
            application.save(
                update_fields=["payment_state", "lifecycle_status", "updated_at"]
            )
            record_application_event(
                application=application,
                event_code="payment.manual_confirmed",
                actor=confirmed_by,
                description=f"Pagamento manual confirmado para {fee.get_fee_type_display()}.",
                metadata={
                    "instrument_id": instrument.pk,
                    "fee_requirement_id": fee.pk,
                    "confirmed_at": now.isoformat(),
                },
            )
        from notifications.services import NotificationService

        NotificationService().notify_payment_confirmed(application, instrument)
        return confirmation


class ModalityChangeService:
    """Gerencia a conversão Projeto <-> Consulta, recalculando taxas e créditos."""

    def __init__(self, fee_service: FeeCalculationService | None = None) -> None:
        self.fee_service = fee_service or FeeCalculationService()

    def convert_to_consultation(
        self,
        *,
        application: ServiceApplication,
        decided_by: Any = None,
        note: str | None = None,
    ) -> None:
        """Converte a inscrição para a modalidade Consulta."""
        with transaction.atomic():
            self._cancel_scheduled_screenings(application, decided_by)
            application.modality = ServiceApplication.Modality.CONSULTATION
            application.dataset_audit_required = False
            application.dataset_audit_state = None
            app_fee = application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            ).first()
            # Paridade com o legado: o ``SUM()`` considerava TODOS os boletos com
            # status 'P' (incluindo a Taxa de Projeto) para deduzir os R$ 140,00.
            # Olhar apenas a taxa de inscrição gerava cobrança indevida (Gap 3).
            total_paid = self._total_paid(application)
            if total_paid >= APPLICATION_FEE_CONSULTATION:
                record_application_event(
                    application=application,
                    event_code="modality.excess_recorded",
                    actor=decided_by,
                    description="Conversão sem cobrança adicional: excesso registrado.",
                    metadata={"paid_amount": str(total_paid)},
                )
            elif app_fee is not None and app_fee.is_paid:
                difference = APPLICATION_FEE_CONSULTATION - total_paid
                if difference > 0:
                    self.fee_service.create_supplement_fee(
                        application,
                        amount=difference,
                    )
                else:
                    record_application_event(
                        application=application,
                        event_code="modality.excess_recorded",
                        actor=decided_by,
                        description="Conversão sem cobrança adicional: excesso registrado.",
                        metadata={"paid_amount": str(total_paid)},
                    )
            elif app_fee is not None:
                self._replace_application_fee(
                    app_fee, APPLICATION_FEE_CONSULTATION
                )
            else:
                self.fee_service.create_application_fee(application)
            # Fluxo sequencial: se ainda houver alguma taxa pendente para
            # Consulta (ex.: complemento de R$ 60), a inscrição aguarda o
            # pagamento; caso contrário, avança para o agendamento.
            pending_fees = [
                fee
                for fee in application.fee_requirements.all()
                if not fee.is_waived and not fee.is_paid
            ]
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
                if not pending_fees
                else ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
            )
            application.save(
                update_fields=[
                    "modality",
                    "dataset_audit_required",
                    "dataset_audit_state",
                    "lifecycle_status",
                    "updated_at",
                ]
            )
            record_application_event(
                application=application,
                event_code="modality.converted_to_consultation",
                actor=decided_by,
                description=note or "Inscrição convertida para Consulta.",
            )
            self._notify_modality_change(application)

    def convert_to_project(
        self,
        *,
        application: ServiceApplication,
        decided_by: Any = None,
        note: str | None = None,
    ) -> None:
        """Converte a inscrição para a modalidade Projeto, aplicando crédito se paga.

        Fluxo sequencial: um Projeto inicia aguardando o pagamento da taxa de
        inscrição. Se essa taxa já estiver paga (ex.: Consulta paga convertida),
        o próximo passo é enviar os dados para auditoria; caso contrário, a
        inscrição aguarda o pagamento.
        """
        with transaction.atomic():
            application.modality = ServiceApplication.Modality.PROJECT
            app_fee = application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            ).first()
            if app_fee is not None and app_fee.is_paid:
                application.modality_credit_amount = CONSULTATION_TO_PROJECT_CREDIT
                fee_paid = True
            elif app_fee is not None:
                self._replace_application_fee(app_fee, APPLICATION_FEE_PROJECT)
                fee_paid = False
            else:
                self.fee_service.create_application_fee(application)
                fee_paid = False
            if application.owner_id is not None:
                application.dataset_audit_required = True
                application.dataset_audit_state = (
                    ServiceApplication.DatasetAuditState.AWAITING_SUBMISSION
                )
                application.lifecycle_status = (
                    ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION
                    if fee_paid
                    else ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
                )
            else:
                application.dataset_audit_required = False
                application.dataset_audit_state = None
                application.lifecycle_status = (
                    ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
                )
            application.save(
                update_fields=[
                    "modality",
                    "modality_credit_amount",
                    "dataset_audit_required",
                    "dataset_audit_state",
                    "lifecycle_status",
                    "updated_at",
                ]
            )
            record_application_event(
                application=application,
                event_code="modality.converted_to_project",
                actor=decided_by,
                description=note or "Inscrição convertida para Projeto.",
            )
            self._notify_modality_change(application)

    @staticmethod
    def _cancel_scheduled_screenings(application: ServiceApplication, canceled_by: Any) -> None:
        """Cancela triagens agendadas antes da conversão para Consulta.

        Paridade com o Laravel: ao trocar a modalidade de Projeto para Consulta,
        o sistema "reseta" os status, mas triagens previamente agendadas
        (``SCHEDULED``/``RESCHEDULED``) não podem ficar órfãs no banco. Cada
        triagem pendente é cancelada via ``ProjectScreeningService.cancel_screening``,
        registrando o evento de auditoria correspondente.
        """
        from meetings.models import ProjectScreening
        from meetings.services import ProjectScreeningService

        screenings = ProjectScreening.objects.filter(application=application).exclude(
            state__in=[
                ProjectScreening.State.CANCELED,
                ProjectScreening.State.COMPLETED,
            ]
        )
        if not screenings.exists():
            return
        service = ProjectScreeningService()
        for screening in screenings:
            service.cancel_screening(screening=screening, canceled_by=canceled_by)

    def _notify_modality_change(self, application: ServiceApplication) -> None:
        """Notifica o candidato sobre a mudança de modalidade (NotifyServiceChange).

        Paridade com o legado: anexa o PDF do boleto ativo da inscrição ao e-mail
        (Gap B), quando disponível.
        """
        from notifications.services import NotificationService

        attachments = self._modality_change_attachments(application)
        NotificationService().notify_modality_changed(
            application, attachments=attachments
        )

    def _modality_change_attachments(
        self, application: ServiceApplication
    ) -> list[dict[str, Any]] | None:
        """Monta o anexo do PDF do boleto ativo da inscrição, se houver."""
        from django.core.files.storage import default_storage

        from bank_slips.models import BankSlipPaymentInstrument

        slip = (
            BankSlipPaymentInstrument.objects.select_related(
                "payment_instrument__fee_requirement", "pdf_asset"
            )
            .filter(
                payment_instrument__fee_requirement__application=application,
                pdf_asset__isnull=False,
            )
            .order_by("-payment_instrument__created_at")
            .first()
        )
        if slip is None or slip.pdf_asset is None:
            return None
        try:
            content = default_storage.open(slip.pdf_asset.storage_key, "rb").read()
        except FileNotFoundError:
            return None
        return [
            {
                "filename": slip.pdf_asset.original_filename,
                "content": content,
                "mimetype": "application/pdf",
            }
        ]

    @staticmethod
    def _total_paid(application: ServiceApplication) -> Decimal:
        """Soma o total efetivamente pago em TODAS as taxas da inscrição."""
        total = Decimal("0.00")
        for fee in application.fee_requirements.all():
            total += fee.paid_amount
        return total

    def _replace_application_fee(
        self, app_fee: FeeRequirement, new_base: Decimal
    ) -> None:
        """Substitui a cobrança de inscrição não paga por um novo valor (TS-FEE-006)."""
        for instrument in app_fee.payment_instruments.filter(
            state__in=[
                PaymentInstrument.State.ACTIVE,
                PaymentInstrument.State.CREATED,
            ]
        ):
            # Paridade com o legado: baixa o boleto antigo no banco via SOAP
            # antes de marcar o instrumento como CANCELADO (Gap A).
            cancel_external_charge(instrument)
            instrument.state = PaymentInstrument.State.CANCELED
            instrument.active_unique_fee_token = None
            instrument.save(
                update_fields=["state", "active_unique_fee_token", "updated_at"]
            )
        app_fee.base_amount = new_base
        app_fee.adjustment_amount = Decimal("0.00")
        app_fee.amount = new_base
        app_fee.save(
            update_fields=["base_amount", "adjustment_amount", "amount", "updated_at"]
        )


class RefundRequestService:
    """Gerencia a criação e transição de solicitações de reembolso."""

    ACTIVE_REFUND_STATUSES = (
        RefundRequest.Status.REQUESTED,
        RefundRequest.Status.APPROVED,
        RefundRequest.Status.EXECUTED,
    )

    def available_for_refund(self, application: ServiceApplication) -> Decimal:
        """Valor ainda reembolsável (pago menos reembolsos já solicitados)."""
        total_paid = self._total_paid(application)
        committed = (
            RefundRequest.objects.filter(
                application=application,
                status__in=self.ACTIVE_REFUND_STATUSES,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        available = total_paid - Decimal(str(committed))
        return available if available > 0 else Decimal("0.00")

    def create_refund_request(
        self,
        *,
        application: ServiceApplication,
        requested_by: Any,
        amount: Decimal,
        reason: str | None = None,
        payment_instrument: PaymentInstrument | None = None,
    ) -> RefundRequest:
        available = self.available_for_refund(application)
        if available <= 0:
            raise PaymentDomainError(
                "Não há valor pago disponível para reembolso nesta inscrição."
            )
        if amount > available:
            raise PaymentDomainError(
                "O valor do reembolso não pode exceder o valor pago disponível "
                f"(R$ {available:.2f})."
            )  # TS-REF-005
        with transaction.atomic():
            refund = RefundRequest.objects.create(
                application=application,
                payment_instrument=payment_instrument,
                status=RefundRequest.Status.REQUESTED,
                amount=amount,
                reason=reason,
                requested_by=requested_by,
            )
            record_application_event(
                application=application,
                event_code="refund.requested",
                actor=requested_by,
                description=f"Solicitação de reembolso de R$ {amount:.2f}.",
                metadata={"refund_request_id": refund.pk, "amount": str(amount)},
            )
        return refund

    def approve(
        self,
        *,
        refund_request: RefundRequest,
        approved_by: Any,
        note: str | None = None,
    ) -> RefundRequest:
        if refund_request.status != RefundRequest.Status.REQUESTED:
            raise PaymentDomainError("Apenas reembolsos solicitados podem ser aprovados.")
        with transaction.atomic():
            refund_request.status = RefundRequest.Status.APPROVED
            refund_request.approved_by = approved_by
            refund_request.approved_at = timezone.now()
            refund_request.note = note or refund_request.note
            refund_request.save(
                update_fields=["status", "approved_by", "approved_at", "note", "updated_at"]
            )
        return refund_request

    def execute(
        self,
        *,
        refund_request: RefundRequest,
        executed_by: Any,
        note: str | None = None,
    ) -> RefundRequest:
        if refund_request.status != RefundRequest.Status.APPROVED:
            raise PaymentDomainError("Apenas reembolsos aprovados podem ser executados.")
        with transaction.atomic():
            refund_request.status = RefundRequest.Status.EXECUTED
            refund_request.executed_by = executed_by
            refund_request.executed_at = timezone.now()
            refund_request.note = note or refund_request.note
            refund_request.save(
                update_fields=["status", "executed_by", "executed_at", "note", "updated_at"]
            )
            refund_request.application.payment_state = (
                ServiceApplication.PaymentState.REFUNDED
            )
            refund_request.application.save(update_fields=["payment_state", "updated_at"])
        return refund_request

    @staticmethod
    def _total_paid(application: ServiceApplication) -> Decimal:
        total = Decimal("0.00")
        for fee in application.fee_requirements.all():
            total += fee.paid_amount
        return total


class OverdueBillingService:
    """Painel de inadimplência: boletos vencidos e cobrança em massa.

    Porta do ``ApplicationController@overdueIndex`` e
    ``ApplicationController@sendOverdueReminders`` do sistema legado.
    """

    def get_overdue_slips(self, term: Any = None):
        """Lista boletos vencidos ainda não pagos (com filtro opcional por semestre)."""
        from bank_slips.models import BankSlipPaymentInstrument

        today = timezone.localdate()
        queryset = (
            BankSlipPaymentInstrument.objects.select_related(
                "payment_instrument__fee_requirement__application"
            )
            .filter(
                due_date__lt=today,
                bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
                payment_instrument__state__in=[
                    PaymentInstrument.State.ACTIVE,
                    PaymentInstrument.State.CREATED,
                ],
            )
            .order_by("due_date")
        )
        if term is not None:
            queryset = queryset.filter(
                payment_instrument__fee_requirement__application__term=term
            )
        return queryset

    def build_overdue_rows(self, term: Any = None) -> list[dict[str, Any]]:
        """Agrupadas por inscrição (paridade com o ``overdue_index`` legado).

        Cada linha representa uma inscrição com boletos vencidos; ``slips`` traz
        os boletos individuais e ``charge_history`` os eventos de cobrança já
        enviados (``payment.overdue_reminder_sent``).
        """
        from applications.models import ApplicationEvent

        slips = list(self.get_overdue_slips(term=term))
        grouped: dict[int, dict[str, Any]] = {}
        for slip in slips:
            application = slip.payment_instrument.fee_requirement.application
            row = grouped.setdefault(
                application.pk,
                {
                    "application": application,
                    "slips": [],
                    "total_due": Decimal("0.00"),
                },
            )
            row["slips"].append(slip)
            row["total_due"] += slip.document_amount or slip.payment_instrument.amount
        charge_events = (
            ApplicationEvent.objects.filter(
                event_code="payment.overdue_reminder_sent",
                application_id__in=list(grouped.keys()),
            )
            .order_by("occurred_at")
            .values_list("application_id", "occurred_at")
        )
        for application_id, occurred_at in charge_events:
            target_row = grouped.get(application_id)
            if target_row is not None:
                target_row.setdefault("charge_history", []).append(occurred_at)
        for row in grouped.values():
            row.setdefault("charge_history", [])
        return list(grouped.values())

    def send_overdue_reminders(self, actor: Any = None, slip_ids: list[int] | None = None) -> int:
        """Dispara e-mails de cobrança; sem ``slip_ids`` usa todos os vencidos."""
        from bank_slips.models import BankSlipPaymentInstrument
        from notifications.services import NotificationService

        notification_service = NotificationService()
        if slip_ids:
            slips = BankSlipPaymentInstrument.objects.filter(
                pk__in=slip_ids
            ).select_related("payment_instrument__fee_requirement__application")
        else:
            slips = self.get_overdue_slips()
        sent = 0
        for slip in slips:
            application = slip.payment_instrument.fee_requirement.application
            notification_service.notify_overdue_reminder(application)
            record_application_event(
                application=application,
                event_code="payment.overdue_reminder_sent",
                actor=actor,
                description="Cobrança de boleto vencido enviada.",
                metadata={"bank_slip_reference": slip.bank_slip_reference},
            )
            sent += 1
        return sent


class PendingPaymentService:
    """Painel de inscrições com taxas pendentes de pagamento."""

    def list_pending_applications(self) -> list[dict[str, Any]]:
        """Lista inscrições que ainda devem alguma taxa.

        A taxa de inscrição é cobrada na criação (Projeto e Consulta),
        independentemente da auditoria de dados. Portanto, qualquer inscrição
        em andamento com pelo menos uma taxa não dispensada e não paga é
        considerada pendente — incluindo Projetos ainda em auditoria.
        """
        applications = (
            ServiceApplication.objects.select_related("term")
            .exclude(
                lifecycle_status__in=[
                    ServiceApplication.LifecycleStatus.NOT_APPROVED,
                    ServiceApplication.LifecycleStatus.CANCELED,
                ]
            )
            .prefetch_related(
                "fee_requirements",
                "fee_requirements__payment_instruments",
            )
            .order_by("protocol")
        )
        rows: list[dict[str, Any]] = []
        for app in applications:
            pending_fees = [
                fee
                for fee in app.fee_requirements.all()
                if not fee.is_waived and not fee.is_paid
            ]
            if not pending_fees:
                continue
            total = sum((fee.amount for fee in pending_fees), Decimal("0.00"))
            rows.append(
                {
                    "application": app,
                    "fees": pending_fees,
                    "total_pending": total,
                }
            )
        return rows
