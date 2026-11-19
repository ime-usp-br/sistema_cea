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
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument(
            "--period",
            default="first",
            choices=["first", "second"],
        )
        parser.add_argument("--submission-start", default=None)
        parser.add_argument("--submission-end", default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        from terms.models import AcademicTerm

        if not settings.DEBUG:
            raise CommandError("e2e_create_term exige DEBUG=True.")
        term, created = AcademicTerm.objects.get_or_create(
            year=options["year"],
            period=options["period"],
            defaults={
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
            },
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
