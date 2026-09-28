"""Serviços de conta do candidato externo (D8).

Cobrem o cadastro com confirmação de e-mail obrigatória e o reenvio do link de
verificação. O token é armazenado apenas como hash, no mesmo padrão do fluxo de
resgate de inscrições legadas.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from .models import EmailVerificationToken, User

TOKEN_EXPIRATION = timedelta(days=2)


class EmailVerificationError(ValueError):
    """Erro de domínio da verificação de e-mail."""


class RegistrationError(ValueError):
    """Erro de domínio do cadastro de candidato."""


def hash_email_token(token: str) -> str:
    """Gera o hash do token de verificação (nunca guarda o valor puro)."""
    payload = f"{token}:{settings.SECRET_KEY}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class EmailVerificationService:
    """Emite, envia e valida tokens de confirmação de e-mail."""

    def issue_token(self, user: User) -> str:
        """Invalida tokens anteriores e emite um novo token puro."""
        now = timezone.now()
        EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
            used_at=now
        )
        raw_token = secrets.token_urlsafe(32)
        EmailVerificationToken.objects.create(
            user=user,
            token_hash=hash_email_token(raw_token),
            expires_at=now + TOKEN_EXPIRATION,
        )
        return raw_token

    def build_verification_url(self, raw_token: str, request: Any = None) -> str:
        path = reverse("users:verify_email", args=[raw_token])
        if request is not None:
            return request.build_absolute_uri(path)
        return path

    def send_verification_email(self, user: User, request: Any = None) -> str:
        """Emite um token e enfileira o e-mail com o link de confirmação."""
        from notifications.services import NotificationService

        raw_token = self.issue_token(user)
        url = self.build_verification_url(raw_token, request)
        NotificationService().notify_email_verification(user, url)
        return raw_token

    def verify(self, raw_token: str) -> User:
        """Confirma o e-mail e consome o token (TS-AUTH-002)."""
        record = (
            EmailVerificationToken.objects.select_related("user")
            .filter(token_hash=hash_email_token(raw_token))
            .first()
        )
        if record is None:
            raise EmailVerificationError("Link de confirmação inválido.")
        if record.used_at is not None:
            raise EmailVerificationError("Este link de confirmação já foi utilizado.")
        now = timezone.now()
        if record.expires_at < now:
            raise EmailVerificationError(
                "Este link de confirmação expirou. Solicite um novo."
            )
        with transaction.atomic():
            user = record.user
            user.is_email_verified = True
            user.email_verified_at = now
            user.save(update_fields=["is_email_verified", "email_verified_at", "updated_at"])
            record.used_at = now
            record.save(update_fields=["used_at"])
        return user

    def resend(self, email: str, request: Any = None) -> None:
        """Reenvia o link de verificação para um cadastro ainda não confirmado."""
        user = User.objects.filter(email__iexact=email.strip()).first()
        if user is None:
            # Não revela se o e-mail existe (evita enumeração de contas).
            return
        if user.is_email_verified:
            return
        self.send_verification_email(user, request)


class RegistrationService:
    """Cria a conta do candidato externo (role ``candidate``)."""

    def __init__(self, verification: EmailVerificationService | None = None) -> None:
        self.verification = verification or EmailVerificationService()

    def register(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
        tax_id: str | None = None,
        request: Any = None,
    ) -> User:
        email = email.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise RegistrationError("Já existe uma conta com este e-mail.")
        try:
            with transaction.atomic():
                user = User(
                    username=email,
                    email=email,
                    full_name=full_name.strip(),
                    tax_id=tax_id or None,
                    role=User.Role.CANDIDATE,
                    is_active=True,
                    is_email_verified=False,
                )
                user.set_password(password)
                user.save()
        except IntegrityError as exc:
            raise RegistrationError("Já existe uma conta com este e-mail.") from exc
        self.verification.send_verification_email(user, request)
        return user
