from decimal import Decimal
from typing import Any

from django.db import transaction
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
    """Avança o fluxo da inscrição após o pagamento da taxa de inscrição (TS-PAY-008)."""
    if application.lifecycle_status != ServiceApplication.LifecycleStatus.AWAITING_PAYMENT:
        return
    if application.modality == ServiceApplication.Modality.PROJECT:
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.AWAITING_SCREENING_SCHEDULING
        )
    else:
        application.lifecycle_status = (
            ServiceApplication.LifecycleStatus.AWAITING_CONSULTATION_SCHEDULING
        )


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
        with transaction.atomic():
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
            application.modality = ServiceApplication.Modality.CONSULTATION
            application.dataset_audit_required = False
            application.dataset_audit_state = None
            app_fee = application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            ).first()
            if app_fee is not None and app_fee.is_paid:
                paid = app_fee.paid_amount
                if paid < APPLICATION_FEE_CONSULTATION:
                    self.fee_service.create_supplement_fee(
                        application,
                        amount=APPLICATION_FEE_CONSULTATION - paid,
                    )
                else:
                    record_application_event(
                        application=application,
                        event_code="modality.excess_recorded",
                        actor=decided_by,
                        description="Conversão sem cobrança adicional: excesso registrado.",
                        metadata={"paid_amount": str(paid)},
                    )
            elif app_fee is not None:
                self._replace_application_fee(
                    app_fee, APPLICATION_FEE_CONSULTATION
                )
            else:
                self.fee_service.create_application_fee(application)
            application.lifecycle_status = (
                ServiceApplication.LifecycleStatus.AWAITING_PAYMENT
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

    def convert_to_project(
        self,
        *,
        application: ServiceApplication,
        decided_by: Any = None,
        note: str | None = None,
    ) -> None:
        """Converte a inscrição para a modalidade Projeto, aplicando crédito se paga."""
        with transaction.atomic():
            application.modality = ServiceApplication.Modality.PROJECT
            app_fee = application.fee_requirements.filter(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            ).first()
            if app_fee is not None and app_fee.is_paid:
                application.modality_credit_amount = CONSULTATION_TO_PROJECT_CREDIT
            elif app_fee is not None:
                self._replace_application_fee(app_fee, APPLICATION_FEE_PROJECT)
            else:
                self.fee_service.create_application_fee(application)
            if application.owner_id is not None:
                application.dataset_audit_required = True
                application.dataset_audit_state = (
                    ServiceApplication.DatasetAuditState.AWAITING_SUBMISSION
                )
                application.lifecycle_status = (
                    ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION
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

    def create_refund_request(
        self,
        *,
        application: ServiceApplication,
        requested_by: Any,
        amount: Decimal,
        reason: str | None = None,
        payment_instrument: PaymentInstrument | None = None,
    ) -> RefundRequest:
        total_paid = self._total_paid(application)
        if amount > total_paid:
            raise PaymentDomainError(
                "O valor do reembolso não pode exceder o valor pago."
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
