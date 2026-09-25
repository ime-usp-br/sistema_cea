"""Testes da resolução de semestre atual (Fase 0, T0.1/T0.2)."""

from __future__ import annotations

from django.test import RequestFactory, TestCase

from terms.models import AcademicTerm
from terms.utils import resolve_term, term_filter_id


class CurrentTermTests(TestCase):
    def test_TS_TRM_CURRENT_ordena_por_ano_desc_segundo_dentro_do_ano(self) -> None:
        AcademicTerm.objects.create(year=2025, period="second")
        AcademicTerm.objects.create(year=2026, period="first")
        expected = AcademicTerm.objects.create(year=2026, period="second")
        self.assertEqual(AcademicTerm.current(), expected)
        self.assertEqual(AcademicTerm.latest(), expected)

    def test_TS_TRM_CURRENT_regressao_first_nao_eh_atual_quando_segundo_existe(
        self,
    ) -> None:
        first = AcademicTerm.objects.create(year=2026, period="first")
        second = AcademicTerm.objects.create(year=2026, period="second")
        # ``Meta.ordering = ["-year", "period"]`` faz ``first()`` retornar o
        # 1º semestre do ano mais recente; ``current()`` corrige isso.
        self.assertEqual(AcademicTerm.objects.first(), first)
        self.assertEqual(AcademicTerm.current(), second)

    def test_TS_TRM_RESOLVE_lhe_term_e_semester_id(self) -> None:
        term = AcademicTerm.objects.create(year=2024, period="first")
        factory = RequestFactory()
        request = factory.get("/", {"term": str(term.pk)})
        self.assertEqual(resolve_term(request), term)
        legacy_request = factory.get("/", {"semester_id": str(term.pk)})
        self.assertEqual(resolve_term(legacy_request), term)

    def test_TS_TRM_RESOLVE_fallback_ao_atual(self) -> None:
        AcademicTerm.objects.create(year=2026, period="first")
        expected = AcademicTerm.objects.create(year=2026, period="second")
        factory = RequestFactory()
        self.assertEqual(resolve_term(factory.get("/")), expected)

    def test_TS_TRM_FILTER_ID_retorna_bruto(self) -> None:
        factory = RequestFactory()
        self.assertEqual(term_filter_id(factory.get("/", {"term": "5"})), "5")
        self.assertEqual(term_filter_id(factory.get("/", {"term": "all"})), "all")
        self.assertIsNone(term_filter_id(factory.get("/")))
