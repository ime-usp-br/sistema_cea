import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from applications.models import ApplicationEvent, ServiceApplication
from payments.services import record_application_event

from .models import LegacyOwnershipClaim

CODE_LENGTH = 6
CODE_EXPIRATION = timedelta(minutes=10)
MAX_VERIFICATION_ATTEMPTS = 5


class LegacyClaimError(ValueError):
    """Erro de domínio para o fluxo de resgate de inscrições legadas."""


def _hash_token(token: str) -> str:
    payload = f"{token}:{settings.SECRET_KEY}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verify_token(claim: LegacyOwnershipClaim, token: str) -> bool:
    if not claim.verification_token_hash:
        return False
    return secrets.compare_digest(
        claim.verification_token_hash, _hash_token(token)
    )


def _count_failed_attempts(claim: LegacyOwnershipClaim) -> int:
    return ApplicationEvent.objects.filter(
        event_code="claim.verification_failed",
        metadata__claim_id=claim.pk,
    ).count()


class LegacyClaimService:
    """Serviço de domínio responsável pelo resgate de inscrições legadas."""

    def request_claim(
        self,
        *,
        user: Any,
        protocol: str,
        contact_email_or_tax_id: str,
    ) -> tuple[LegacyOwnershipClaim, str]:
        """Localiza a inscrição importada e envia código de confirmação (TS-CLAIM-001/002)."""
        identifier = (contact_email_or_tax_id or "").strip()
        application = self._find_imported_application(protocol, identifier)
        if application is None:
            raise LegacyClaimError(
                "Nenhuma inscrição importada foi encontrada com os dados informados."
            )
        if application.owner_id is not None:
            raise LegacyClaimError("Esta inscrição já possui um dono vinculado.")

        # Invalida pedidos anteriores ainda ativos para a mesma inscrição
        # (TS-CLAIM-GAP-001): evita acúmulo de códigos válidos e e-mails/spam.
        self._invalidate_previous_claims(application)

        token = self._generate_code()
        now = timezone.now()
        claim = LegacyOwnershipClaim.objects.create(
            user=user,
            application=application,
            protocol=application.protocol,
            contact_email=application.legacy_contact_email or application.contact_email,
            contact_tax_id=application.legacy_contact_tax_id,
            status=LegacyOwnershipClaim.Status.CODE_SENT,
            verification_token_hash=_hash_token(token),
            code_expires_at=now + CODE_EXPIRATION,
        )
        self._send_code_email(claim, token)
        return claim, token

    def confirm_claim(
        self,
        *,
        user: Any,
        claim_id: int,
        code: str,
    ) -> LegacyOwnershipClaim:
        """Confirma o código e vincula a inscrição ao usuário (TS-CLAIM-003/004/005)."""
        claim = self._get_claim_for_user(user, claim_id)
        if claim.status not in {
            LegacyOwnershipClaim.Status.PENDING,
            LegacyOwnershipClaim.Status.CODE_SENT,
        }:
            raise LegacyClaimError("Esta solicitação de resgate não está ativa.")
        if claim.code_expires_at is None or timezone.now() > claim.code_expires_at:
            claim.status = LegacyOwnershipClaim.Status.REJECTED
            claim.save(update_fields=["status", "updated_at"])
            raise LegacyClaimError("O código de verificação expirou.")

        if not _verify_token(claim, code.strip()):
            self._record_failed_attempt(claim)
            if _count_failed_attempts(claim) >= MAX_VERIFICATION_ATTEMPTS:
                claim.status = LegacyOwnershipClaim.Status.REJECTED
                claim.save(update_fields=["status", "updated_at"])
                raise LegacyClaimError(
                    "Limite de tentativas excedido. Solicite um novo código."
                )
            raise LegacyClaimError("O código informado está incorreto.")

        application = claim.application
        if application is None:
            raise LegacyClaimError("A reivindicação não possui inscrição vinculada.")
        with transaction.atomic():
            application.owner = user
            application.save(update_fields=["owner", "updated_at"])
            now = timezone.now()
            claim.status = LegacyOwnershipClaim.Status.VERIFIED
            claim.verified_at = now
            claim.verification_token_hash = None
            claim.code_expires_at = None
            claim.save(
                update_fields=[
                    "status",
                    "verified_at",
                    "verification_token_hash",
                    "code_expires_at",
                    "updated_at",
                ]
            )
            record_application_event(
                application=application,
                event_code="claim.verified",
                actor=user,
                description="Inscrição legada resgatada pelo candidato.",
                metadata={"claim_id": claim.pk},
            )
        return claim

    def manually_approve_claim(
        self,
        *,
        claim: LegacyOwnershipClaim,
        secretariat_user: Any,
        note: str | None = None,
    ) -> LegacyOwnershipClaim:
        """Aprovação manual de resgate pela secretaria (TS-CLAIM-007)."""
        if claim.application is None:
            raise LegacyClaimError("A reivindicação não possui inscrição vinculada.")
        if claim.application.owner_id is not None:
            raise LegacyClaimError("Esta inscrição já possui um dono vinculado.")
        with transaction.atomic():
            claim.application.owner = claim.user
            claim.application.save(update_fields=["owner", "updated_at"])
            now = timezone.now()
            claim.status = LegacyOwnershipClaim.Status.MANUALLY_APPROVED
            claim.verified_at = now
            claim.reviewed_by = secretariat_user
            claim.review_note = note
            claim.verification_token_hash = None
            claim.code_expires_at = None
            claim.save(
                update_fields=[
                    "status",
                    "verified_at",
                    "reviewed_by",
                    "review_note",
                    "verification_token_hash",
                    "code_expires_at",
                    "updated_at",
                ]
            )
            record_application_event(
                application=claim.application,
                event_code="claim.manually_approved",
                actor=secretariat_user,
                description=note or "Inscrição legada resgatada manualmente pela secretaria.",
                metadata={"claim_id": claim.pk},
            )
        return claim

    # ---- helpers ----

    def _find_imported_application(
        self, protocol: str, identifier: str
    ) -> ServiceApplication | None:
        qs = (
            ServiceApplication.all_objects.filter(
                origin=ServiceApplication.Origin.IMPORTED,
                owner__isnull=True,
                soft_deleted_at__isnull=True,
            )
            .select_related("term")
            .all()
        )
        protocol = (protocol or "").strip()
        identifier = identifier.lower()
        for app in qs:
            email_match = bool(
                app.legacy_contact_email
                and app.legacy_contact_email.lower() == identifier
            )
            tax_match = bool(
                app.legacy_contact_tax_id
                and app.legacy_contact_tax_id.lower() == identifier
            )
            protocol_match = bool(protocol and app.protocol == protocol)
            if protocol_match or email_match or tax_match:
                return app
        return None

    def _generate_code(self) -> str:
        return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"

    def _invalidate_previous_claims(self, application: ServiceApplication) -> None:
        """Rejeita pedidos de resgate anteriores ainda ativos da mesma inscrição."""
        active = LegacyOwnershipClaim.objects.filter(
            application=application,
            status__in=[
                LegacyOwnershipClaim.Status.PENDING,
                LegacyOwnershipClaim.Status.CODE_SENT,
            ],
        )
        for claim in active:
            claim.status = LegacyOwnershipClaim.Status.REJECTED
            claim.verification_token_hash = None
            claim.code_expires_at = None
            claim.save(
                update_fields=[
                    "status",
                    "verification_token_hash",
                    "code_expires_at",
                    "updated_at",
                ]
            )

    def _send_code_email(self, claim: LegacyOwnershipClaim, token: str) -> None:
        legacy_email = (
            claim.application.legacy_contact_email if claim.application else None
        )
        recipient = claim.contact_email or legacy_email
        if not recipient:
            raise LegacyClaimError(
                "Não há e-mail de contato cadastrado para enviar o código."
            )
        send_mail(
            subject="Código de resgate de inscrição",
            message=(
                f"Seu código de resgate é: {token}\n"
                f"Ele é válido por 10 minutos e deve ser usado "
                "para vincular sua inscrição."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
        )

    def _get_claim_for_user(self, user: Any, claim_id: int) -> LegacyOwnershipClaim:
        try:
            return LegacyOwnershipClaim.objects.select_related("application").get(
                pk=claim_id, user_id=user.pk
            )
        except LegacyOwnershipClaim.DoesNotExist as exc:
            raise LegacyClaimError("Solicitação de resgate não encontrada.") from exc

    def _record_failed_attempt(self, claim: LegacyOwnershipClaim) -> None:
        if claim.application is not None:
            ApplicationEvent.objects.create(
                application=claim.application,
                event_code="claim.verification_failed",
                actor=claim.user,
                description="Tentativa de verificação de código incorreta.",
                metadata={"claim_id": claim.pk},
            )
