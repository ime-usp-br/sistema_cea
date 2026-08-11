from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

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
