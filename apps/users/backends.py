import os

from django.contrib.auth.backends import ModelBackend
from django.urls import reverse
from django.utils import timezone
from senhaunica_socialite.backends import SenhaUnicaBackend
from senhaunica_socialite.client import SenhaUnicaClient

from users.models import IdentityProviderLink, User


class EmailVerifiedModelBackend(ModelBackend):
    """Login local que aceita e-mail ou usuário e exige e-mail confirmado (D8).

    Substitui o ``ModelBackend`` quando ``ENABLE_LOCAL_LOGIN`` está ligado. A
    conta criada pelo cadastro externo só autentica após confirmar o e-mail;
    Senha Única continua marcando ``is_email_verified=True``.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        resolved = self._resolve_username(username)
        user = super().authenticate(
            request, username=resolved, password=password, **kwargs
        )
        if user is None:
            return None
        if not self.user_can_authenticate(user):
            return None
        if not (
            user.is_email_verified or user.is_superuser or user.is_staff
        ):
            return None
        return user

    @staticmethod
    def _resolve_username(identifier: str) -> str:
        """Permite login por e-mail (fallback para o username)."""
        if User.objects.filter(username=identifier).exists():
            return identifier
        match = (
            User.objects.filter(email__iexact=identifier)
            .values_list("username", flat=True)
            .first()
        )
        return match or identifier


class CustomSenhaUnicaBackend(SenhaUnicaBackend):
    """Backend da Senha Única USP com enriquecimento do cadastro do usuário.

    Além de criar/logar o usuário via OAuth da USP, garante que:

    - ``codpes`` (número USP) seja gravado no campo próprio do ``User``;
    - ``full_name`` seja preenchido a partir do nome retornado pela USP;
    - o login via Senha Única conte como e-mail verificado
      (``is_email_verified`` + ``email_verified_at``);
    - o vínculo de identidade (``IdentityProviderLink``) seja criado/atualizado.
    """

    def authenticate(self, request, oauth_token=None, oauth_token_secret=None, oauth_verifier=None, **kwargs):
        if not oauth_token or not oauth_verifier or not oauth_token_secret:
            return None

        key = os.getenv("SENHAUNICA_KEY")
        secret = os.getenv("SENHAUNICA_SECRET")
        if not key or not secret:
            return None

        try:
            callback = request.build_absolute_uri(reverse("senhaunica_callback"))
        except Exception:
            callback = "http://localhost:8000/callback"
        callback_id = os.getenv("SENHAUNICA_CALLBACK_ID")
        env = os.getenv("SENHAUNICA_ENV", "prod")

        client = SenhaUnicaClient(key, secret, callback, callback_id=callback_id, env=env)

        try:
            token_resp = client.fetch_access_token(
                oauth_token, oauth_token_secret, oauth_verifier
            )
            access_token = token_resp["oauth_token"]
            access_token_secret = token_resp["oauth_token_secret"]

            user_info = client.get_user_info(access_token, access_token_secret)

            codpes_raw = user_info.get("loginUsuario") or user_info.get("codpes")
            if not codpes_raw:
                return None

            email = (
                user_info.get("emailPrincipalUsuario")
                or user_info.get("emailUspUsuario")
                or user_info.get("email")
                or ""
            )
            nome = user_info.get("nomeUsuario") or user_info.get("nompes") or ""

            codpes = int(codpes_raw)
            now = timezone.now()
            user, _ = User.objects.get_or_create(
                username=str(codpes),
                defaults={
                    "codpes": codpes,
                    "email": email,
                    "is_email_verified": True,
                    "email_verified_at": now,
                },
            )

            user.codpes = codpes
            user.full_name = nome or user.full_name
            user.first_name = nome or user.first_name
            user.email = email or user.email
            user.is_email_verified = True
            if not user.email_verified_at:
                user.email_verified_at = now
            user.save()

            IdentityProviderLink.objects.update_or_create(
                user=user,
                provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
                defaults={
                    "external_id": str(codpes),
                    "external_email": email,
                },
            )

            return user
        except Exception:
            return None
