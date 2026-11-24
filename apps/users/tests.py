from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import IdentityProviderLink

User = get_user_model()


class UserModelTests(TestCase):
    def test_custom_user_model_exists(self) -> None:
        self.assertEqual(User._meta.label, "users.User")

    def test_user_has_identity_fields(self) -> None:
        user = User.objects.create_user(
            username="aluno",
            email="aluno@usp.br",
            full_name="Aluno Teste",
            tax_id="12345678900",
            codpes=123456,
        )
        self.assertEqual(user.full_name, "Aluno Teste")
        self.assertEqual(user.tax_id, "12345678900")
        self.assertEqual(user.codpes, 123456)
        self.assertFalse(user.is_email_verified)
        self.assertIsNone(user.email_verified_at)
        self.assertIsNotNone(user.created_at)

    def test_user_email_is_unique(self) -> None:
        User.objects.create_user(username="aluno1", email="dup@usp.br")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(username="aluno2", email="dup@usp.br")


class IdentityProviderLinkTests(TestCase):
    def test_identity_provider_link_creation(self) -> None:
        user = User.objects.create_user(username="aluno", email="aluno@usp.br")
        link = IdentityProviderLink.objects.create(
            user=user,
            provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
            external_id="123456",
            external_email="aluno@usp.br",
        )
        self.assertEqual(link.user, user)
        self.assertEqual(link.provider, "usp_senha_unica")
        self.assertIsNotNone(link.linked_at)

    def test_TS_AUTH_005_vincula_identidade_a_usuario_existente_sem_duplicar(self) -> None:
        user = User.objects.create_user(
            username="aluno",
            email="aluno@usp.br",
            is_email_verified=True,
        )
        IdentityProviderLink.objects.create(
            user=user,
            provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
            external_id="123456",
            external_email="aluno@usp.br",
        )
        self.assertEqual(User.objects.filter(email="aluno@usp.br").count(), 1)
        link = IdentityProviderLink.objects.get(
            provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
            external_id="123456",
        )
        self.assertEqual(link.user, user)

    def test_unique_user_provider_constraint(self) -> None:
        user = User.objects.create_user(username="aluno", email="aluno@usp.br")
        IdentityProviderLink.objects.create(
            user=user,
            provider=IdentityProviderLink.Provider.LOCAL,
            external_id="x",
        )
        with self.assertRaises(IntegrityError):
            IdentityProviderLink.objects.create(
                user=user,
                provider=IdentityProviderLink.Provider.LOCAL,
                external_id="y",
            )


class CustomSenhaUnicaBackendTests(TestCase):
    user_info = {
        "loginUsuario": "123456",
        "nomeUsuario": "Maria da Silva",
        "emailPrincipalUsuario": "maria@usp.br",
    }

    def _request(self):
        request = type(
            "Request", (), {"build_absolute_uri": lambda self, u: f"http://test/{u}"}
        )()
        return request

    def _settings(self):
        return override_settings(
            SENHAUNICA_KEY="key",
            SENHAUNICA_SECRET="secret",
            SENHAUNICA_CALLBACK_ID="cb",
        )

    def test_login_cadastra_codpes_full_name_e_marca_email_verificado(self) -> None:
        from users.backends import CustomSenhaUnicaBackend

        with (
            self._settings(),
            patch(
                "users.senhaunica.SenhaUnicaClient.get_user_info",
                return_value=self.user_info,
            ),
            patch(
                "users.senhaunica.SenhaUnicaClient.fetch_access_token",
                return_value={"oauth_token": "t", "oauth_token_secret": "s"},
            ),
        ):
            user = CustomSenhaUnicaBackend().authenticate(
                self._request(),
                oauth_token="tok",
                oauth_verifier="ver",
                oauth_token_secret="sec",
            )

        self.assertIsNotNone(user)
        self.assertEqual(user.codpes, 123456)
        self.assertEqual(user.full_name, "Maria da Silva")
        self.assertTrue(user.is_email_verified)
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(
            IdentityProviderLink.objects.filter(
                user=user,
                provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
                external_id="123456",
            ).exists()
        )

    def test_login_atualiza_usuario_existente_e_nao_duplica_vinculo(self) -> None:
        from users.backends import CustomSenhaUnicaBackend

        user = User.objects.create_user(
            username="123456",
            email="antigo@usp.br",
            codpes=123456,
            full_name="Antigo Nome",
        )
        IdentityProviderLink.objects.create(
            user=user,
            provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
            external_id="123456",
        )

        with (
            self._settings(),
            patch(
                "users.senhaunica.SenhaUnicaClient.get_user_info",
                return_value=self.user_info,
            ),
            patch(
                "users.senhaunica.SenhaUnicaClient.fetch_access_token",
                return_value={"oauth_token": "t", "oauth_token_secret": "s"},
            ),
        ):
            result = CustomSenhaUnicaBackend().authenticate(
                self._request(),
                oauth_token="tok",
                oauth_verifier="ver",
                oauth_token_secret="sec",
            )

        user.refresh_from_db()
        self.assertEqual(result, user)
        self.assertEqual(user.full_name, "Maria da Silva")
        self.assertEqual(user.email, "maria@usp.br")
        self.assertTrue(user.is_email_verified)
        self.assertEqual(
            IdentityProviderLink.objects.filter(
                user=user,
                provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
            ).count(),
            1,
        )

    def test_TS_AUTH_005_vincula_por_email_sem_criar_conta_duplicada(self) -> None:
        from users.backends import CustomSenhaUnicaBackend

        local = User.objects.create_user(
            username="maria-local",
            email="maria@usp.br",
            is_email_verified=True,
        )
        with (
            self._settings(),
            patch(
                "users.senhaunica.SenhaUnicaClient.get_user_info",
                return_value=self.user_info,
            ),
            patch(
                "users.senhaunica.SenhaUnicaClient.fetch_access_token",
                return_value={"oauth_token": "t", "oauth_token_secret": "s"},
            ),
        ):
            result = CustomSenhaUnicaBackend().authenticate(
                self._request(),
                oauth_token="tok",
                oauth_verifier="ver",
                oauth_token_secret="sec",
            )

        local.refresh_from_db()
        self.assertEqual(result, local)
        self.assertEqual(local.username, "maria-local")
        self.assertEqual(local.codpes, 123456)
        self.assertEqual(User.objects.filter(email="maria@usp.br").count(), 1)
        self.assertTrue(
            IdentityProviderLink.objects.filter(
                user=local,
                provider=IdentityProviderLink.Provider.USP_SENHA_UNICA,
                external_id="123456",
            ).exists()
        )


class RoleGroupSyncTests(TestCase):
    def test_role_secretariat_sincroniza_grupo_ao_criar(self) -> None:
        user = User.objects.create_user(
            username="sec1",
            email="sec1@example.com",
            role=User.Role.SECRETARIAT,
        )
        self.assertEqual(
            set(user.groups.values_list("name", flat=True)), {"secretariat"}
        )

    def test_mudanca_de_role_atualiza_grupos(self) -> None:
        user = User.objects.create_user(
            username="muda1",
            email="muda1@example.com",
            role=User.Role.TEACHER,
        )
        user.role = User.Role.ADMINISTRATOR
        user.save()
        user.refresh_from_db()
        self.assertEqual(
            set(user.groups.values_list("name", flat=True)), {"administrator"}
        )

    def test_papel_invalido_nao_cria_grupo(self) -> None:
        user = User.objects.create(
            username="invalido",
            email="invalido@example.com",
            role="nao_existe",
        )
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.groups.count(), 0)


@override_settings(
    SENHAUNICA_KEY="key",
    SENHAUNICA_SECRET="secret",
    SENHAUNICA_CALLBACK_ID="1",
    SENHAUNICA_ENV="dev",
    SENHAUNICA_OAUTH_BASE_URL="http://senhaunica-faker:3141/wsusuario/oauth",
)
class SenhaUnicaFakerIntegrationTests(TestCase):
    """Login OAuth1 apontando para o uspdev/senhaunica-faker (stack E2E)."""

    def test_login_init_usa_endpoints_do_faker(self) -> None:
        with patch(
            "users.senhaunica.SenhaUnicaClient.fetch_request_token",
            return_value={
                "oauth_token": "request-token",
                "oauth_token_secret": "request-secret",
            },
        ):
            response = self.client.get(reverse("users:senhaunica_login"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "http://senhaunica-faker:3141/wsusuario/oauth/authorize", response.url
        )
        self.assertIn("oauth_token=request-token", response.url)
        self.assertEqual(
            self.client.session["senhaunica_token_secret"], "request-secret"
        )

    def test_callback_autentica_usuario_do_faker(self) -> None:
        session = self.client.session
        session["senhaunica_token_secret"] = "request-secret"
        session.save()
        with (
            patch(
                "users.senhaunica.SenhaUnicaClient.fetch_access_token",
                return_value={
                    "oauth_token": "1600001",
                    "oauth_token_secret": "access-secret",
                },
            ),
            patch(
                "users.senhaunica.SenhaUnicaClient.get_user_info",
                return_value={
                    "loginUsuario": "1600001",
                    "nomeUsuario": "Aluno Faker",
                    "emailPrincipalUsuario": "aluno.faker@usp.br",
                },
            ),
        ):
            response = self.client.get(
                reverse("users:senhaunica_callback"),
                {"oauth_token": "request-token", "oauth_verifier": "1600001"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        self.assertIn("_auth_user_id", self.client.session)
        user = User.objects.get(username="1600001")
        self.assertEqual(user.codpes, 1600001)
        self.assertEqual(user.full_name, "Aluno Faker")
        self.assertTrue(user.is_email_verified)

    def test_callback_sem_sessao_retorna_400(self) -> None:
        response = self.client.get(
            reverse("users:senhaunica_callback"),
            {"oauth_token": "request-token", "oauth_verifier": "1600001"},
        )
        self.assertEqual(response.status_code, 400)

    def test_login_init_sem_credenciais_retorna_500(self) -> None:
        with override_settings(SENHAUNICA_KEY="", SENHAUNICA_SECRET=""):
            response = self.client.get(reverse("users:senhaunica_login"))
        self.assertEqual(response.status_code, 500)
