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

    # TS-ADM-SEC-TERMOS
    def test_TS_ADM_SECRETARIA_acessa_semestres_e_emails(self) -> None:
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

    # TS-ADM-SEC-NAO-USUARIOS (Secretaria não gerencia usuários: sem add/change)
    def test_TS_ADM_SECRETARIA_nao_acessa_usuarios(self) -> None:
        self._login(self.secretariat)
        self.assertFalse(self.secretariat.has_perm("users.add_user"))
        self.assertFalse(self.secretariat.has_perm("users.change_user"))
        response = self.client.get(reverse("admin:users_user_add"))
        self.assertNotEqual(response.status_code, 200)

    # TS-ADM-ADMIN-TUDO
    def test_TS_ADM_ADMIN_acessa_tudo(self) -> None:
        # O Administrador do Django padrão precisa de superuser OU permissões
        # via grupos; o ``ensure_secretariat_admin_permissions`` só trata a
        # Secretaria, então elevamos o Admin local via superuser.
        self.admin.is_superuser = True
        self.admin.save()
        self._login(self.admin)
        self.assertEqual(
            self.client.get(reverse("admin:users_user_changelist")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("admin:terms_academicterm_changelist")).status_code,
            200,
        )
