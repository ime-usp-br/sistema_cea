from datetime import date
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Semeia de forma idempotente os dados mínimos necessários para os testes "
        "E2E de navegador: um período letivo e um candidato com credenciais conhecidas. "
        "As opções de catálogo já são criadas pela migration 0003_seed_catalog_options."
    )

    E2E_USERNAME = "e2e_candidate"
    E2E_PASSWORD = "e2e-senha-123"
    E2E_EMAIL = "e2e_candidate@example.com"

    def handle(self, *args: Any, **options: Any) -> None:
        from applications.models import CatalogOption
        from terms.models import AcademicTerm
        from users.models import User

        term, term_created = AcademicTerm.objects.get_or_create(
            year=2099,
            period=AcademicTerm.Period.FIRST,
            defaults={
                "submission_start_date": date.today(),
                "submission_end_date": date(2099, 12, 31),
            },
        )

        user, user_created = User.objects.get_or_create(
            username=self.E2E_USERNAME,
            defaults={
                "email": self.E2E_EMAIL,
                "full_name": "Candidato E2E",
                "is_active": True,
                "is_email_verified": True,
            },
        )
        if user_created:
            user.set_password(self.E2E_PASSWORD)
            user.save()

        catalog_count = CatalogOption.objects.count()
        if catalog_count == 0:
            self.stderr.write(
                "Nenhuma opção de catálogo encontrada. Execute as migrações "
                "(manage.py migrate) para popular catalog_options."
            )
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Período {term} ({'criado' if term_created else 'existente'}), "
                f"candidato '{self.E2E_USERNAME}' ({'criado' if user_created else 'existente'}), "
                f"{catalog_count} opções de catálogo disponíveis."
            )
        )
