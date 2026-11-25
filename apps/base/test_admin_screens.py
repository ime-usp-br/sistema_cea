"""Cobertura ampla das telas do Django admin (TST-BASE-014/015/016)."""

from __future__ import annotations

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from applications.factories import ApplicationFactory
from terms.factories import AcademicTermFactory
from users.factories import UserFactory


class AdminScreenCoverageTests(TestCase):
    def setUp(self) -> None:
        self.admin_user = UserFactory.create(
            username="admin-cobertura",
            email="admin-cobertura@example.com",
            role="administrator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)
        AcademicTermFactory.create()
        ApplicationFactory.create()

    # TST-BASE-014
    def test_todas_as_listagens_do_admin_respondem(self) -> None:
        for model in admin.site._registry:
            opts = model._meta
            url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"changelist {url}")

    # TST-BASE-015
    def test_todas_as_telas_de_criacao_do_admin_respondem(self) -> None:
        for model in admin.site._registry:
            opts = model._meta
            url = reverse(f"admin:{opts.app_label}_{opts.model_name}_add")
            response = self.client.get(url)
            self.assertNotIn(
                response.status_code, {404, 500}, f"add {url}"
            )

    # TST-BASE-016
    def test_telas_de_edicao_e_exclusao_do_admin_respondem(self) -> None:
        for model in admin.site._registry:
            manager = getattr(model, "objects", None)
            if manager is None:
                continue
            instance = manager.first()
            if instance is None:
                continue
            opts = model._meta
            change_url = reverse(
                f"admin:{opts.app_label}_{opts.model_name}_change",
                args=[instance.pk],
            )
            delete_url = reverse(
                f"admin:{opts.app_label}_{opts.model_name}_delete",
                args=[instance.pk],
            )
            self.assertEqual(
                self.client.get(change_url).status_code, 200, f"change {change_url}"
            )
            self.assertEqual(
                self.client.get(delete_url).status_code, 200, f"delete {delete_url}"
            )
