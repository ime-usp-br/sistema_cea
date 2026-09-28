from datetime import date
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Semeia de forma idempotente os dados mínimos necessários para os testes "
        "E2E de navegador: um período letivo e os usuários candidato/docente/secretaria "
        "com credenciais conhecidas. As opções de catálogo já são criadas pela migration "
        "0003_seed_catalog_options."
    )

    E2E_PASSWORD = "e2e-senha-123"

    E2E_USERNAME = "e2e_candidate"
    E2E_EMAIL = "e2e_candidate@example.com"
    E2E_TEACHER_USERNAME = "e2e_teacher"
    E2E_TEACHER_EMAIL = "e2e_teacher@example.com"
    E2E_SECRETARIAT_USERNAME = "e2e_secretariat"
    E2E_SECRETARIAT_EMAIL = "e2e_secretariat@example.com"

    def handle(self, *args: Any, **options: Any) -> None:
        from applications.models import CatalogOption
        from terms.models import AcademicTerm
        from users.models import User
        from users.permissions_sync import ensure_secretariat_admin_permissions

        term, term_created = AcademicTerm.objects.get_or_create(
            year=2099,
            period=AcademicTerm.Period.FIRST,
            defaults={
                "submission_start_date": date.today(),
                "submission_end_date": date(2099, 12, 31),
            },
        )

        candidate, candidate_created = self._ensure_user(
            username=self.E2E_USERNAME,
            email=self.E2E_EMAIL,
            full_name="Candidato E2E",
            role=User.Role.CANDIDATE,
        )
        teacher, teacher_created = self._ensure_user(
            username=self.E2E_TEACHER_USERNAME,
            email=self.E2E_TEACHER_EMAIL,
            full_name="Docente E2E",
            role=User.Role.TEACHER,
        )
        secretariat, secretariat_created = self._ensure_user(
            username=self.E2E_SECRETARIAT_USERNAME,
            email=self.E2E_SECRETARIAT_EMAIL,
            full_name="Secretaria E2E",
            role=User.Role.SECRETARIAT,
        )
        # Secretaria precisa de is_staff/permissões restritas de admin.
        ensure_secretariat_admin_permissions()

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
                f"candidato '{candidate.username}' ({'criado' if candidate_created else 'existente'}), "
                f"docente '{teacher.username}' ({'criado' if teacher_created else 'existente'}), "
                f"secretaria '{secretariat.username}' ({'criado' if secretariat_created else 'existente'}), "
                f"{catalog_count} opções de catálogo disponíveis."
            )
        )

    def _ensure_user(
        self, *, username: str, email: str, full_name: str, role: str
    ) -> tuple[Any, bool]:
        from users.models import User

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "full_name": full_name,
                "role": role,
                "is_active": True,
                "is_email_verified": True,
            },
        )
        # Garante invariantes do E2E mesmo em bancos já semeados por versões
        # anteriores (login local agora exige e-mail confirmado — D8).
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if user.role != role:
            user.role = role
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if not user.is_email_verified:
            user.is_email_verified = True
            changed = True
        user.set_password(self.E2E_PASSWORD)
        changed = True
        if changed:
            user.save()
        return user, created
