from typing import Any

from django.core.management.base import BaseCommand

from applications.factories import ApplicationFactory
from users.factories import UserFactory


class Command(BaseCommand):
    help = (
        "Popula o banco de DEV com candidatos e inscrições válidas (dados "
        "anonimizados via Faker). As inscrições são "
        "criadas pelo Service Layer para respeitar a máquina de estados e gerar eventos."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--users", type=int, default=20, help="Número de usuários candidatos.")
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="Número de inscrições criadas (distribuídas entre os usuários).",
        )
        parser.add_argument(
            "--modality",
            type=str,
            default="",
            choices=["project", "consultation"],
            help="Restringe a modalidade das inscrições (padrão: misto).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from datetime import date

        from applications.models import ServiceApplication
        from terms.models import AcademicTerm

        next_year = date.today().year + 1
        term, _created = AcademicTerm.objects.get_or_create(
            year=next_year,
            period=AcademicTerm.Period.FIRST,
            defaults={"submission_start_date": date.today()},
        )
        users = [UserFactory() for _ in range(options["users"])]
        self.stdout.write(
            self.style.SUCCESS(f"Período {term} e {len(users)} candidatos criados.")
        )

        created = 0
        for i in range(options["count"]):
            kwargs = {"term": term, "owner": users[i % len(users)]}
            if options["modality"]:
                kwargs["modality"] = options["modality"]
            ApplicationFactory.create(**kwargs)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} inscrições criadas. "
                f"Total no banco: {ServiceApplication.objects.count()}."
            )
        )
