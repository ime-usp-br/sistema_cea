"""Testes do cadastro, confirmação de e-mail e recuperação de senha (D8)."""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from notifications.models import NotificationDispatch
from users.models import EmailVerificationToken, User
from users.services import (
    EmailVerificationError,
    EmailVerificationService,
    RegistrationError,
    RegistrationService,
)

EAGER = override_settings(CELERY_TASK_ALWAYS_EAGER=True)


@EAGER
class CandidateAccountTests(TestCase):
    def setUp(self) -> None:
        self.verification = EmailVerificationService()

    def test_TS_AUTH_002_cadastro_bloqueia_login_ate_confirmar(self) -> None:
        url = reverse("users:signup")
        response = self.client.post(
            url,
            {
                "full_name": "Nova Candidata",
                "email": "nova@example.com",
                "tax_id": "",
                "password1": "senha-forte-123",
                "password2": "senha-forte-123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="nova@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertTrue(
            NotificationDispatch.objects.filter(
                template__code="email_verification"
            ).exists()
        )

        # Login bloqueado antes da confirmação, com mensagem clara.
        response = self.client.post(
            reverse("login"),
            {"username": "nova@example.com", "password": "senha-forte-123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirme seu e-mail")

        # Confirma e o login funciona.
        raw_token = self.verification.send_verification_email(user)
        response = self.client.get(reverse("users:verify_email", args=[raw_token]))
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertIsNotNone(user.email_verified_at)

        self.assertTrue(
            self.client.login(username="nova@example.com", password="senha-forte-123")
        )

    def test_TS_AUTH_002_token_invalido_e_expirado(self) -> None:
        user = User.objects.create_user(
            username="tok@example.com",
            email="tok@example.com",
            password="senha-forte-123",
        )
        raw_token = self.verification.issue_token(user)
        # Token errado.
        response = self.client.get(reverse("users:verify_email", args=["token-errado"]))
        self.assertEqual(response.status_code, 400)
        # Token expirado.
        EmailVerificationToken.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.client.get(reverse("users:verify_email", args=[raw_token]))
        self.assertEqual(response.status_code, 400)

    def test_TS_AUTH_002_email_duplicado_rejeitado(self) -> None:
        User.objects.create_user(
            username="dup@example.com", email="dup@example.com", password="x"
        )
        with self.assertRaises(RegistrationError):
            RegistrationService().register(
                full_name="Duplicada",
                email="DUP@example.com",
                password="senha-forte-123",
            )

    def test_TS_AUTH_002_token_uso_unico(self) -> None:
        user = User.objects.create_user(
            username="once@example.com",
            email="once@example.com",
            password="senha-forte-123",
        )
        raw_token = self.verification.issue_token(user)
        self.verification.verify(raw_token)
        with self.assertRaises(EmailVerificationError):
            self.verification.verify(raw_token)

    def test_TS_AUTH_006_recuperacao_de_senha_templates_resolvem(self) -> None:
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recuperar senha")

        user = User.objects.create_user(
            username="reset@example.com",
            email="reset@example.com",
            password="senha-forte-123",
            is_email_verified=True,
        )
        response = self.client.post(reverse("password_reset"), {"email": user.email})
        self.assertEqual(response.status_code, 302)
        done = self.client.get(response.headers["Location"])
        self.assertEqual(done.status_code, 200)

        # Fluxo completo de definição da nova senha (templates resolvem).
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_url = reverse("password_reset_confirm", args=[uid, token])
        response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            response.headers["Location"],
            {"new_password1": "outra-senha-456", "new_password2": "outra-senha-456"},
        )
        self.assertEqual(response.status_code, 302)
        complete = self.client.get(response.headers["Location"])
        self.assertEqual(complete.status_code, 200)
        self.assertContains(complete, "Senha redefinida")

    def test_TS_AUTH_002_reenvio_nao_revela_email(self) -> None:
        response = self.client.post(
            reverse("users:resend_verification"),
            {"email": "inexistente@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Se existir uma conta pendente")
