from django.contrib.auth.backends import ModelBackend
from django.utils import timezone
from senhaunica_socialite.backends import SenhaUnicaBackend

from users.models import IdentityProviderLink, User
from users.senhaunica import get_senhaunica_client


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

        client = get_senhaunica_client(request)
        if client is None:
            return None

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

            user = User.objects.filter(codpes=codpes).first() or User.objects.filter(
                username=str(codpes)
            ).first()
            if user is None and email:
                email_user = User.objects.filter(email__iexact=email).first()
                if email_user is not None:
                    # Só vincula uma conta local já confirmada; e-mail não
                    # verificado não é prova suficiente de identidade.
                    if (
                        not email_user.is_email_verified
                        or email_user.codpes not in (None, codpes)
                    ):
                        return None
                    user = email_user

            if user is None:
                user = User.objects.create(
                    username=str(codpes),
                    codpes=codpes,
                    email=email,
                    is_email_verified=True,
                    email_verified_at=now,
                )
            else:
                if user.codpes not in (None, codpes):
                    return None
                user.codpes = codpes

            user.full_name = nome or user.full_name
            user.first_name = nome or user.first_name
            user.email = email or user.email
            user.is_email_verified = True
            if not user.email_verified_at:
                user.email_verified_at = now
            user.save()

            conflicting_link = (
                IdentityProviderLink.objects.filter(
                    provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
                    external_id=str(codpes),
                )
                .exclude(user=user)
                .exists()
            )
            if conflicting_link:
                return None

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
