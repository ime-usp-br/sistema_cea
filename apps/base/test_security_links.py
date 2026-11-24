"""Testes de segurança de links e esquemas (TS-SEC-005/007)."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from audits.forms import DatasetSubmissionForm


class SecurityLinkTests(TestCase):
    def test_TS_SEC_005_todos_links_nova_aba_tem_noopener(self) -> None:
        root = Path(settings.BASE_DIR) / "templates"
        offenders: list[str] = []
        for path in root.rglob("*.html"):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if 'target="_blank"' in line and not re.search(
                    r'rel="[^"]*noopener[^"]*noreferrer', line
                ):
                    offenders.append(f"{path.relative_to(root)}:{number}")
        self.assertEqual(offenders, [])

    def test_TS_SEC_005_rejeita_esquema_perigoso_no_link_de_auditoria(self) -> None:
        form = DatasetSubmissionForm(
            data={
                "channel": "external_link",
                "external_url": "javascript:alert(1)",
                "external_link_declaration": "on",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("external_url", form.errors)
