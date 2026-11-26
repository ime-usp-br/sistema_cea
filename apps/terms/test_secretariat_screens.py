"""Telas dedicadas da Secretaria para gestão de semestres (TST-TERM-009..013)."""

from __future__ import annotations

from datetime import date

from django.test import TestCase
from django.urls import reverse

from terms.models import AcademicTerm
from users.factories import (
    AdministratorFactory,
    SecretariatFactory,
    UserFactory,
)


class SecretariatTermScreensTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTerm.objects.create(
            year=2026,
            period=AcademicTerm.Period.FIRST,
        )
        self.secretariat = SecretariatFactory.create()
        self.admin = AdministratorFactory.create()
        self.candidate = UserFactory.create()

    def _valid_payload(self, **overrides):
        payload = {
            "year": 2027,
            "period": AcademicTerm.Period.SECOND,
            "teaching_start_date": "2027-08-01",
            "teaching_end_date": "2027-12-15",
            "submission_start_date": "2027-06-01",
            "submission_end_date": "2027-07-31",
        }
        payload.update(overrides)
        return payload

    # TST-TERM-009
    def test_TST_TERM_009_lista_semestres_para_secretaria(self) -> None:
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("terms:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semestres")
        self.assertContains(response, "2026")
        self.assertContains(response, "Primeiro Semestre")

    # TST-TERM-010
    def test_TST_TERM_010_secretaria_cadastra_semestre_pela_pagina(self) -> None:
        self.client.force_login(self.secretariat)
        response = self.client.post(reverse("terms:create"), self._valid_payload())
        self.assertRedirects(response, reverse("terms:list"))
        term = AcademicTerm.objects.get(year=2027, period=AcademicTerm.Period.SECOND)
        self.assertEqual(term.teaching_start_date, date(2027, 8, 1))
        self.assertEqual(term.submission_end_date, date(2027, 7, 31))

    # TST-TERM-011
    def test_TST_TERM_011_secretaria_edita_semestre_pela_pagina(self) -> None:
        self.client.force_login(self.secretariat)
        response = self.client.post(
            reverse("terms:update", args=[self.term.pk]),
            self._valid_payload(
                year=2026,
                period=AcademicTerm.Period.FIRST,
                teaching_start_date="2026-02-02",
                teaching_end_date="2026-06-30",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.term.refresh_from_db()
        self.assertEqual(self.term.teaching_start_date, date(2026, 2, 2))
        self.assertEqual(self.term.teaching_end_date, date(2026, 6, 30))

    # TST-TERM-012
    def test_TST_TERM_012_candidato_nao_acessa_gestao_de_semestres(self) -> None:
        self.client.force_login(self.candidate)
        for url in (
            reverse("terms:list"),
            reverse("terms:create"),
            reverse("terms:update", args=[self.term.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    # TST-TERM-013
    def test_TST_TERM_013_valida_ordem_das_datas(self) -> None:
        self.client.force_login(self.secretariat)
        response = self.client.post(
            reverse("terms:create"),
            self._valid_payload(
                teaching_start_date="2027-12-15",
                teaching_end_date="2027-08-01",
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "A data final não pode ser anterior à data inicial.",
        )
        self.assertFalse(
            AcademicTerm.objects.filter(year=2027, period="second").exists()
        )

    # TST-TERM-014
    def test_TST_TERM_014_administrador_acessa_gestao_de_semestres(self) -> None:
        self.client.force_login(self.admin)
        response = self.client.get(reverse("terms:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get(reverse("terms:create")).status_code,
            200,
        )
