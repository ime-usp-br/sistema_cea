"""Cria um período letivo e imprime os dados em JSON (setup E2E).

A criação dispara o ``post_save`` real de ``AcademicTerm`` (migração de
transferências pendentes), exatamente como a tela do admin faria.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria um período letivo para o E2E e emite JSON (somente DEBUG)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--year", type=int)
        parser.add_argument(
            "--period",
            default="first",
            choices=["first", "second"],
        )
        parser.add_argument("--submission-start", default=None)
        parser.add_argument("--submission-end", default=None)
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Aloca o próximo ano livre no namespace E2E.",
        )
        parser.add_argument(
            "--peek",
            action="store_true",
            help="Apenas informa o próximo ano livre do namespace, sem criar.",
        )
        parser.add_argument("--namespace-start", type=int, default=9000)
        parser.add_argument("--namespace-end", type=int, default=9999)

    def _next_free_year(self, *, start: int, end: int, period: str) -> int:
        from terms.models import AcademicTerm

        used = list(
            AcademicTerm.objects.filter(
                year__gte=start, year__lte=end, period=period
            ).values_list("year", flat=True)
        )
        year = max(used) + 1 if used else start
        if year > end:
            raise CommandError(
                f"Namespace E2E esgotado ({start}-{end}). Recrie o banco da stack E2E."
            )
        return year

    def handle(self, *args: Any, **options: Any) -> None:
        from terms.models import AcademicTerm

        if not settings.DEBUG:
            raise CommandError("e2e_create_term exige DEBUG=True.")
        if options["peek"]:
            year = self._next_free_year(
                start=options["namespace_start"],
                end=options["namespace_end"],
                period=options["period"],
            )
            self.stdout.write(json.dumps({"year": year}))
            return
        defaults = {
            "submission_start_date": (
                date.fromisoformat(options["submission_start"])
                if options["submission_start"]
                else date.today()
            ),
            "submission_end_date": (
                date.fromisoformat(options["submission_end"])
                if options["submission_end"]
                else None
            ),
        }
        if options["year"] is None:
            if not options["auto"]:
                raise CommandError("Informe --year ou use --auto.")
            # Em caso de corrida entre dois testes, o segundo get_or_create
            # retorna created=False; nesse caso aloca o próximo ano livre.
            while True:
                year = self._next_free_year(
                    start=options["namespace_start"],
                    end=options["namespace_end"],
                    period=options["period"],
                )
                term, created = AcademicTerm.objects.get_or_create(
                    year=year,
                    period=options["period"],
                    defaults=defaults,
                )
                if created:
                    break
        else:
            term, created = AcademicTerm.objects.get_or_create(
                year=options["year"],
                period=options["period"],
                defaults=defaults,
            )
        self.stdout.write(
            json.dumps(
                {
                    "id": term.pk,
                    "year": term.year,
                    "period": term.period,
                    "created": created,
                    "submission_start_date": (
                        term.submission_start_date.isoformat()
                        if term.submission_start_date
                        else None
                    ),
                    "submission_end_date": (
                        term.submission_end_date.isoformat()
                        if term.submission_end_date
                        else None
                    ),
                }
            )
        )
