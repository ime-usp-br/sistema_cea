import base64
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from files.services import create_file_asset_from_bytes
from payments.models import FeeRequirement, PaymentInstrument
from payments.services import (
    PaymentOrchestrationService,
    advance_lifecycle_after_application_fee,
    record_application_event,
    refresh_payment_state,
)

from .gateways import BankSlipGateway
from .models import BankSlipPaymentInstrument


class BankSlipDomainError(ValueError):
    """Erro de domínio do módulo de boletos."""


class BankSlipPaymentService:
    """Orquestra a emissão, sincronização e cancelamento de boletos."""

    def __init__(
        self,
        gateway: BankSlipGateway | None = None,
        orchestration: PaymentOrchestrationService | None = None,
    ) -> None:
        self.gateway = gateway or BankSlipGateway()
        self.orchestration = orchestration or PaymentOrchestrationService()

    def _payer_data(self, application) -> tuple[str, str, str]:
        doc = application.tax_id or ""
        if not doc and application.owner_id is not None:
            owner = application.owner
            doc = getattr(owner, "tax_id", "") or ""
        digits = "".join(ch for ch in str(doc) if ch.isdigit())
        tipo = "PJ" if len(digits) > 11 else "PF"
        return tipo, digits, application.researcher_name

    def generate_bank_slip_for_fee(
        self,
        *,
        fee_requirement: FeeRequirement,
        created_by: Any = None,
    ) -> BankSlipPaymentInstrument:
        """Gera (ou reutiliza) um boleto ativo para uma taxa (TS-BSL-001/002)."""
        if fee_requirement.is_paid:
            raise BankSlipDomainError(
                "A taxa já foi paga e não permite gerar um novo boleto."
            )
        now = timezone.now()
        active = fee_requirement.payment_instruments.filter(
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
        ).first()
        if active is not None:
            slip = getattr(active, "bank_slip_instrument", None)
            if slip is not None:
                return slip

        application = fee_requirement.application
        tipo, cpf_cnpj, nome = self._payer_data(application)
        due = now.date() + timedelta(days=settings.BANK_SLIP_DUE_DAYS)
        valor = f"{fee_requirement.amount:.2f}"
        payload = {
            "codigoUnidadeDespesa": settings.BANK_SLIP_CODIGO_UNIDADE_DESPESA,
            "codigoFonteRecurso": settings.BANK_SLIP_CODIGO_FONTE_RECURSO,
            "estruturaHierarquica": settings.BANK_SLIP_ESTRUTURA_HIERARQUICA,
            "valorDocumento": valor,
            "dataVencimentoBoleto": due.strftime("%d/%m/%Y"),
            "tipoSacado": tipo,
            "cpfCnpj": cpf_cnpj,
            "nomeSacado": nome,
            "instrucoesObjetoCobranca": "Pagamento referente à taxa de inscrição.",
        }
        result = self.gateway.gerar_boleto(payload)
        reference = str(result.get("codigoIDBoleto", ""))
        if not reference:
            raise BankSlipDomainError("O gateway não retornou um codigoIDBoleto válido.")

        payment_instrument = self.orchestration.create_payment_instrument(
            fee_requirement=fee_requirement,
            method=PaymentInstrument.Method.BANK_SLIP.value,
            created_by=created_by,
        )
        with transaction.atomic():
            slip = BankSlipPaymentInstrument.objects.create(
                payment_instrument=payment_instrument,
                bank_slip_reference=reference,
                due_date=due,
                bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
                document_amount=fee_requirement.amount,
                discount_amount=result.get("valorDesconto") or Decimal("0.00"),
                registration_date=now.date(),
            )
            record_application_event(
                application=application,
                event_code="bank_slip.generated",
                actor=created_by,
                description=f"Boleto gerado ({reference}).",
                metadata={
                    "bank_slip_reference": reference,
                    "amount": valor,
                    "due_date": due.isoformat(),
                },
            )
        return slip

    def _store_pdf(
        self,
        application,
        uploaded_by: Any,
        reference: str,
        pdf_base64: str,
    ):
        try:
            content = base64.b64decode(pdf_base64)
        except (ValueError, TypeError):
            return None
        return create_file_asset_from_bytes(
            application=application,
            uploaded_by=uploaded_by,
            content=content,
            filename=f"boleto-{reference}.pdf",
            content_type="application/pdf",
            purpose="bank_slip_pdf",
        )

    def sync_bank_slip_status(self, slip: BankSlipPaymentInstrument) -> None:
        """Consulta a situação no gateway e atualiza o estado local (TS-BSL-003)."""
        status = self.gateway.obter_situacao(slip.bank_slip_reference).upper()
        instrument = slip.payment_instrument
        if status == "P":
            self._confirm_paid(slip)
        elif status == "V":
            if instrument.state != PaymentInstrument.State.PAID:
                self._mark_requires_review(slip)
        elif status == "C":
            self._mark_canceled(slip)
        else:
            slip.bank_status = BankSlipPaymentInstrument.BankStatus.EMITTED
            slip.save(update_fields=["bank_status", "updated_at"])

    def _confirm_paid(self, slip: BankSlipPaymentInstrument) -> None:
        instrument = slip.payment_instrument
        if instrument.state == PaymentInstrument.State.PAID:
            return
        fee = instrument.fee_requirement
        application = fee.application
        now = timezone.now()
        with transaction.atomic():
            instrument.state = PaymentInstrument.State.PAID
            instrument.paid_at = now
            instrument.save(update_fields=["state", "paid_at", "updated_at"])
            slip.bank_status = BankSlipPaymentInstrument.BankStatus.PAID
            slip.paid_amount = slip.document_amount or instrument.amount
            slip.payment_date = now.date()
            slip.save(
                update_fields=[
                    "bank_status",
                    "paid_amount",
                    "payment_date",
                    "updated_at",
                ]
            )
            refresh_payment_state(application)
            advance_lifecycle_after_application_fee(application)
            application.save(
                update_fields=["payment_state", "lifecycle_status", "updated_at"]
            )
            record_application_event(
                application=application,
                event_code="bank_slip.paid",
                description=f"Boleto {slip.bank_slip_reference} pago.",
                metadata={
                    "bank_slip_reference": slip.bank_slip_reference,
                    "paid_at": now.isoformat(),
                },
            )

    def _mark_requires_review(self, slip: BankSlipPaymentInstrument) -> None:
        instrument = slip.payment_instrument
        application = instrument.fee_requirement.application
        with transaction.atomic():
            instrument.state = PaymentInstrument.State.REQUIRES_REVIEW
            instrument.save(update_fields=["state", "updated_at"])
            slip.bank_status = BankSlipPaymentInstrument.BankStatus.VERIFY
            slip.save(update_fields=["bank_status", "updated_at"])
            record_application_event(
                application=application,
                event_code="bank_slip.requires_review",
                description=f"Boleto {slip.bank_slip_reference} requer revisão (status V).",
                metadata={"bank_slip_reference": slip.bank_slip_reference},
            )

    def _mark_canceled(self, slip: BankSlipPaymentInstrument) -> None:
        instrument = slip.payment_instrument
        with transaction.atomic():
            if instrument.state == PaymentInstrument.State.ACTIVE:
                instrument.state = PaymentInstrument.State.CANCELED
                instrument.save(update_fields=["state", "updated_at"])
            slip.bank_status = BankSlipPaymentInstrument.BankStatus.CANCELED
            slip.cancellation_date = timezone.now().date()
            slip.save(update_fields=["bank_status", "cancellation_date", "updated_at"])

    def cancel_bank_slip(self, slip: BankSlipPaymentInstrument) -> None:
        """Cancela um boleto ativo/emitido no gateway (TS-BSL-007)."""
        instrument = slip.payment_instrument
        if instrument.state == PaymentInstrument.State.PAID:
            raise BankSlipDomainError("Um boleto pago não pode ser cancelado.")
        self.gateway.cancelar_boleto(slip.bank_slip_reference)
        with transaction.atomic():
            if instrument.state == PaymentInstrument.State.ACTIVE:
                instrument.state = PaymentInstrument.State.CANCELED
                instrument.save(update_fields=["state", "updated_at"])
            slip.bank_status = BankSlipPaymentInstrument.BankStatus.CANCELED
            slip.cancellation_date = timezone.now().date()
            slip.save(update_fields=["bank_status", "cancellation_date", "updated_at"])
            record_application_event(
                application=instrument.fee_requirement.application,
                event_code="bank_slip.canceled",
                description=f"Boleto {slip.bank_slip_reference} cancelado.",
                metadata={"bank_slip_reference": slip.bank_slip_reference},
            )

    def simulate_payment(self, slip: BankSlipPaymentInstrument) -> None:
        """Simula o pagamento de um boleto em desenvolvimento (TS-BSL-010)."""
        if not settings.DEBUG:
            raise BankSlipDomainError(
                "Simulação de pagamento só é permitida em desenvolvimento."
            )
        self._confirm_paid(slip)

    def fetch_pdf(self, slip: BankSlipPaymentInstrument):
        """Baixa e armazena o PDF do boleto via ``obterBoleto`` (TS-BSL-006).

        Contrato WS-Boleto (docs/BOLETO.md): o método ``obterBoleto`` retorna o
        campo ``boletoPDF`` com o PDF em Base64.
        """
        if slip.pdf_asset is not None:
            return slip.pdf_asset
        result = self.gateway.obter_boleto_pdf(slip.bank_slip_reference)
        pdf_b64 = (
            result.get("boletoPDF") or result.get("pdfBase64")
            if isinstance(result, dict)
            else result
        )
        asset = self._store_pdf(
            slip.payment_instrument.fee_requirement.application,
            None,
            slip.bank_slip_reference,
            str(pdf_b64),
        )
        if asset is not None:
            slip.pdf_asset = asset
            slip.save(update_fields=["pdf_asset", "updated_at"])
        return asset
