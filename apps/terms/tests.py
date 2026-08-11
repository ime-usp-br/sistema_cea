from datetime import date

from django.db import IntegrityError
from django.test import TestCase

from terms.models import AcademicTerm


class AcademicTermTests(TestCase):
    def test_term_creation(self) -> None:
        term = AcademicTerm.objects.create(
            year=2026,
            period=AcademicTerm.Period.FIRST,
            submission_start_date=date(2026, 2, 1),
            submission_end_date=date(2026, 3, 31),
        )
        self.assertEqual(term.year, 2026)
        self.assertEqual(term.period, "first")
        self.assertEqual(term.submission_start_date, date(2026, 2, 1))
        self.assertEqual(term.submission_end_date, date(2026, 3, 31))
        self.assertIsNotNone(term.created_at)

    def test_unique_year_period_constraint(self) -> None:
        AcademicTerm.objects.create(year=2026, period=AcademicTerm.Period.FIRST)
        with self.assertRaises(IntegrityError):
            AcademicTerm.objects.create(year=2026, period=AcademicTerm.Period.FIRST)

    def test_term_str(self) -> None:
        term = AcademicTerm.objects.create(year=2026, period=AcademicTerm.Period.SECOND)
        self.assertEqual(str(term), "2026 - Segundo Semestre")
