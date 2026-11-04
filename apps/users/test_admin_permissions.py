"""Testes de permissões de admin para a Secretaria (Fase 7, T7.2)."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from notifications.models import NotificationTemplate
from terms.models import AcademicTerm
from users.models import User
from users.permissions_sync import ensure_secretariat_admin_permissions


class SecretariatAdminPermissionsTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.template = NotificationTemplate.objects.create(
            code="test_code",
            name="Template Teste",
            audience="candidate",
            subject="Assunto",
            body="Corpo",
            is_active=True,
        )
        self.secretariat = User.objects.create_user(
            username="sec",
            email="sec@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.admin = User.objects.create_user(
            username="adm",
            email="adm@example.com",
            password="pass",
            role=User.Role.ADMINISTRATOR,
        )
        ensure_secretariat_admin_permissions()
        self.secretariat.refresh_from_db()
        self.admin.refresh_from_db()

    def _login(self, user: User) -> None:
        self.client.force_login(user)

    # TS-SEC-008 — Secretaria acessa apenas Semestres e E-mails no admin
    def test_TS_SEC_008_secretaria_acessa_semestres_e_emails(self) -> None:
        self._login(self.secretariat)
        self.secretariat.refresh_from_db()
        self.assertTrue(self.secretariat.is_staff)
        self.assertTrue(self.secretariat.has_perm("terms.view_academicterm"))
        terms_response = self.client.get(
            reverse("admin:terms_academicterm_changelist")
        )
        self.assertEqual(terms_response.status_code, 200, terms_response.headers)
        templates_response = self.client.get(
            reverse("admin:notifications_notificationtemplate_changelist")
        )
        self.assertEqual(templates_response.status_code, 200)

    # TS-SEC-008 — Secretaria não gerencia usuários (sem add/change)
    def test_TS_SEC_008_secretaria_nao_acessa_usuarios(self) -> None:
        self._login(self.secretariat)
        self.assertFalse(self.secretariat.has_perm("users.add_user"))
        self.assertFalse(self.secretariat.has_perm("users.change_user"))
        response = self.client.get(reverse("admin:users_user_add"))
        self.assertNotEqual(response.status_code, 200)

    # TS-SEC-008 — o Administrador recebe acesso total via grupo RBAC
    def test_TS_SEC_008_admin_acessa_tudo(self) -> None:
        self._login(self.admin)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)
        self.assertTrue(self.admin.has_perm("users.add_user"))
        self.assertTrue(self.admin.has_perm("users.change_user"))
        self.assertTrue(self.admin.has_perm("terms.change_academicterm"))
        self.assertEqual(
            self.client.get(reverse("admin:users_user_changelist")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("admin:terms_academicterm_changelist")).status_code,
            200,
        )
