import base64
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from applications.models import ServiceApplication
from files.services import create_file_asset_from_bytes
from payments.models import FeeRequirement, PaymentInstrument
from payments.services import (
    PaymentOrchestrationService,
    advance_lifecycle_after_application_fee,
    record_application_event,
    refresh_payment_state,
)

from .gateways import PixGateway
from .models import PixPaymentInstrument, PixWebhookEvent

# Imagem PNG 1x1 usada como placeholder para o QR Code em ambientes de
# desenvolvimento/teste (sem dependência de biblioteca de geração de QR).
_QR_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class PixPaymentDomainError(ValueError):
    """Erro de domínio do módulo Pix."""


def parse_ptbr_amount(raw: str | None) -> Decimal | None:
    """Converte um valor em pt-BR (ex: '80,00') para Decimal."""
    if raw is None:
        return None
    try:
        return Decimal(str(raw).replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def format_ptbr_amount(value: Decimal) -> str:
    """Formata um Decimal para o formato pt-BR (ex: '80,00')."""
    return f"{value:.2f}".replace(".", ",")


def _qrcode_png_bytes(_payload: str) -> bytes:
    return _QR_PLACEHOLDER_PNG


def _qrcode_image_content(result: dict[str, Any], payload: str) -> bytes:
    """Extrai a imagem do QR Code retornada pelo gateway.

    Contrato WSPIX (docs/PIX.md): ``POST /pix/gerar`` retorna ``qrCodeImgBase64``
    com a imagem do QR Code codificada em Base64. Em dev/teste (sem a imagem),
    usa-se o placeholder.
    """
    raw = result.get("qrCodeImgBase64")
    if raw:
        try:
            return base64.b64decode(raw)
        except (ValueError, TypeError):
            pass
    return _qrcode_png_bytes(payload)


class PixPaymentService:
    """Orquestra a geração, consulta e recebimento de pagamentos Pix."""

    def __init__(
        self,
        gateway: PixGateway | None = None,
        orchestration: PaymentOrchestrationService | None = None,
    ) -> None:
        self.gateway = gateway or PixGateway()
        self.orchestration = orchestration or PaymentOrchestrationService()

    def _payer_data(self, application: ServiceApplication) -> tuple[str, str, str]:
        doc = application.tax_id or ""
        if not doc and application.owner_id is not None:
            owner = application.owner
            doc = getattr(owner, "tax_id", "") or ""
        digits = "".join(ch for ch in str(doc) if ch.isdigit())
        tipo_pessoa = "PJ" if len(digits) > 11 else "PF"
        nome = application.researcher_name
        return tipo_pessoa, digits, nome

    def generate_pix_for_fee(
        self,
        *,
        fee_requirement: FeeRequirement,
        created_by: Any = None,
    ) -> PixPaymentInstrument:
        """Gera (ou reutiliza) um Pix ativo para uma taxa (TS-PIX-001/002)."""
        if fee_requirement.is_paid:
            raise PixPaymentDomainError(
                "A taxa já foi paga e não permite gerar um novo Pix."
            )
        now = timezone.now()
        active = fee_requirement.payment_instruments.filter(
            method=PaymentInstrument.Method.PIX,
            state=PaymentInstrument.State.ACTIVE,
        ).first()
        if active is not None:
            pix = getattr(active, "pix_instrument", None)
            if pix is not None and pix.expires_at and pix.expires_at > now:
                return pix

        application = fee_requirement.application
        tipo_pessoa, doc, nome = self._payer_data(application)
        protocol = application.protocol
        payload = {
            "tipoPessoa": tipo_pessoa,
            "docPesOrg": doc,
            "nomePesOrg": nome,
            "valor": format_ptbr_amount(fee_requirement.amount),
            "infoCobranca": f"CEA {protocol} {fee_requirement.get_fee_type_display()}",
            "expiracao": settings.PIX_EXPIRATION_SECONDS,
            "codigoFonteRecurso": settings.PIX_CODIGO_FONTE_RECURSO,
            "codigoUnidadeDespesa": settings.PIX_CODIGO_UNIDADE_DESPESA,
            "estruturaHierarquica": settings.PIX_ESTRUTURA_HIERARQUICA,
        }
        result = self.gateway.generate_pix(payload)

        payment_instrument = self.orchestration.create_payment_instrument(
            fee_requirement=fee_requirement,
            method=PaymentInstrument.Method.PIX.value,
            created_by=created_by,
        )
        pix_reference = str(result.get("idfpix", ""))
        if not pix_reference:
            raise PixPaymentDomainError("O gateway não retornou um idfpix válido.")

        generated_at = now
        expires_at = now + timedelta(seconds=settings.PIX_EXPIRATION_SECONDS)
        with transaction.atomic():
            pix = PixPaymentInstrument.objects.create(
                payment_instrument=payment_instrument,
                pix_reference=pix_reference,
                qr_code_payload=str(
                    result.get("qrCode") or result.get("qr_code_payload") or ""
                ),
                external_status=str(result.get("status", "ativo")),
                generated_at=generated_at,
                expires_at=expires_at,
                payer_name=result.get("payer_name") or nome,
                payer_tax_id=result.get("payer_tax_id") or doc,
                bank_return_code=result.get("retornoBancario"),
            )
            image = create_file_asset_from_bytes(
                application=application,
                uploaded_by=created_by,
                content=_qrcode_image_content(result, pix.qr_code_payload),
                filename=f"qrcode-pix-{protocol}.png",
                content_type="image/png",
                purpose="pix_qrcode_image",
            )
            pix.qr_code_image_asset = image
            pix.save(update_fields=["qr_code_image_asset", "updated_at"])
            record_application_event(
                application=application,
                event_code="pix.generated",
                actor=created_by,
                description=f"Pix gerado ({pix_reference}).",
                metadata={
                    "pix_reference": pix_reference,
                    "amount": str(fee_requirement.amount),
                    "expires_at": expires_at.isoformat(),
                },
            )
        return pix

    def process_webhook_payload(
        self,
        *,
        raw_payload: dict[str, Any],
        token: str | None,
    ) -> PixWebhookEvent:
        """Processa o payload de webhook do Pix (idempotente)."""
        expected = settings.PIX_WEBHOOK_TOKEN
        token_valid = bool(token) and token == expected
        pix_reference = str(raw_payload.get("idfpix", ""))
        event = PixWebhookEvent.objects.create(
            pix_reference=pix_reference,
            raw_payload=raw_payload,
            token_valid=token_valid,
            processed=False,
        )

        if not token_valid:
            event.error_message = "Token inválido."
            event.processed = True
            event.save(update_fields=["processed", "error_message"])
            return event  # TS-PIX-005

        pix = (
            PixPaymentInstrument.objects.select_related(
                "payment_instrument__fee_requirement__application"
            )
            .filter(pix_reference=pix_reference)
            .first()
        )
        if pix is None:
            event.error_message = "Pix desconhecido."
            event.processed = True
            event.save(update_fields=["processed", "error_message"])
            return event  # TS-PIX-008

        status = str(raw_payload.get("status", "")).lower()
        if pix.payment_instrument.state == PaymentInstrument.State.PAID:
            event.processed = True
            event.save(update_fields=["processed"])
            return event  # TS-PIX-006 (idempotência)

        if status != "pago":
            event.processed = True
            event.save(update_fields=["processed"])
            return event

        received_amount = parse_ptbr_amount(raw_payload.get("valor"))
        expected_amount = pix.payment_instrument.amount
        if received_amount is None or received_amount != expected_amount:
            self._mark_requires_review(pix, "Valor divergente no webhook.", event)
            return event  # TS-PIX-007

        self._confirm_payment(pix, event, received_amount)
        return event

    def _confirm_payment(
        self,
        pix: PixPaymentInstrument,
        event: PixWebhookEvent,
        amount: Decimal,
    ) -> None:
        instrument = pix.payment_instrument
        fee = instrument.fee_requirement
        application = fee.application
        now = timezone.now()
        with transaction.atomic():
            instrument.state = PaymentInstrument.State.PAID
            instrument.paid_at = now
            instrument.save(update_fields=["state", "paid_at", "updated_at"])
            pix.paid_at = now
            pix.external_status = "pago"
            pix.save(update_fields=["paid_at", "external_status", "updated_at"])
            refresh_payment_state(application)
            advance_lifecycle_after_application_fee(application)
            application.save(
                update_fields=["payment_state", "lifecycle_status", "updated_at"]
            )
            event.processed = True
            event.error_message = None
            event.save(update_fields=["processed", "error_message"])
            record_application_event(
                application=application,
                event_code="pix.confirmed",
                description=f"Pix {pix.pix_reference} confirmado: R$ {amount:.2f}.",
                metadata={
                    "pix_reference": pix.pix_reference,
                    "amount": str(amount),
                    "paid_at": now.isoformat(),
                },
            )

    def _mark_requires_review(
        self,
        pix: PixPaymentInstrument,
        reason: str,
        event: PixWebhookEvent,
    ) -> None:
        instrument = pix.payment_instrument
        application = instrument.fee_requirement.application
        with transaction.atomic():
            instrument.state = PaymentInstrument.State.REQUIRES_REVIEW
            instrument.save(update_fields=["state", "updated_at"])
            pix.external_status = "requires_review"
            pix.save(update_fields=["external_status", "updated_at"])
            event.processed = True
            event.error_message = reason
            event.save(update_fields=["processed", "error_message"])
            record_application_event(
                application=application,
                event_code="pix.requires_review",
                description=reason,
                metadata={"pix_reference": pix.pix_reference},
            )

    def check_pix_status(self, pix: PixPaymentInstrument) -> None:
        """Consulta o status no gateway e atualiza o estado local (TS-PIX-003)."""
        data = self.gateway.check_pix_status(pix.pix_reference)
        status = str(data.get("status", "")).lower()
        if status == "pago" and pix.payment_instrument.state != PaymentInstrument.State.PAID:
            amount = parse_ptbr_amount(data.get("valor"))
            event = PixWebhookEvent.objects.create(
                pix_reference=pix.pix_reference,
                raw_payload=data,
                token_valid=True,
                processed=False,
            )
            if amount == pix.payment_instrument.amount:
                self._confirm_payment(pix, event, amount)
            else:
                self._mark_requires_review(
                    pix, "Valor divergente na consulta.", event
                )

    def simulate_payment(self, pix: PixPaymentInstrument) -> None:
        """Simula o pagamento de um Pix em ambiente de desenvolvimento (TS-PIX-010)."""
        if not settings.DEBUG:
            raise PixPaymentDomainError(
                "Simulação de pagamento só é permitida em desenvolvimento."
            )
        if pix.payment_instrument.state == PaymentInstrument.State.PAID:
            return
        event = PixWebhookEvent.objects.create(
            pix_reference=pix.pix_reference,
            raw_payload={"simulacao": True},
            token_valid=True,
            processed=False,
        )
        self._confirm_payment(pix, event, pix.payment_instrument.amount)

    def expire_stale_pix(self) -> int:
        """Expira Pix ativos cuja validade já passou (TS-PIX-002 / TS-PAY-007)."""
        now = timezone.now()
        stale = PixPaymentInstrument.objects.select_for_update().filter(
            expires_at__lt=now,
            payment_instrument__state=PaymentInstrument.State.ACTIVE,
        )
        count = 0
        for pix in stale:
            with transaction.atomic():
                pix.payment_instrument.state = PaymentInstrument.State.EXPIRED
                pix.payment_instrument.save(update_fields=["state", "updated_at"])
                pix.external_status = "expirado"
                pix.save(update_fields=["external_status", "updated_at"])
            count += 1
        return count

    def reconcile_completed_pix(self, start_date: str, end_date: str) -> int:
        """Concilia Pix pagos usando ``listarConcluidos`` (TS-PIX-009)."""
        from datetime import datetime

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as exc:
            raise PixPaymentDomainError("Datas inválidas para reconciliação.") from exc
        if (end.date() - start.date()).days > settings.PIX_RECONCILIATION_MAX_DAYS:
            raise PixPaymentDomainError(
                "O período de reconciliação não pode exceder "
                f"{settings.PIX_RECONCILIATION_MAX_DAYS} dias."
            )
        # Contrato WSPIX (docs/PIX.md): listarConcluidos usa dtaini/dtafim no
        # formato dd/MM/aaaa hh:mm:ss.
        dtaini = start.strftime("%d/%m/%Y 00:00:00")
        dtafim = end.strftime("%d/%m/%Y 23:59:59")
        completed = self.gateway.list_completed_pix(dtaini, dtafim)
        count = 0
        for item in completed:
            ref = str(item.get("idfpix", ""))
            pix = (
                PixPaymentInstrument.objects.select_related(
                    "payment_instrument__fee_requirement__application"
                )
                .filter(pix_reference=ref)
                .first()
            )
            if pix is None or pix.payment_instrument.state == PaymentInstrument.State.PAID:
                continue
            amount = parse_ptbr_amount(item.get("valor"))
            event = PixWebhookEvent.objects.create(
                pix_reference=ref,
                raw_payload=item,
                token_valid=True,
                processed=False,
            )
            if amount == pix.payment_instrument.amount:
                self._confirm_payment(pix, event, amount)
                count += 1
        return count
