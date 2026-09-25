from django.core.management.base import BaseCommand

from users.permissions_sync import ensure_secretariat_admin_permissions


class Command(BaseCommand):
    help = (
        "Garante is_staff=True e permissões restritas de admin (Semestres, "
        "Modelos de E-mail) para o papel Secretaria. Idempotente."
    )

    def handle(self, *args, **options):
        result = ensure_secretariat_admin_permissions()
        self.stdout.write(
            self.style.SUCCESS(
                "Permissões de admin sincronizadas: "
                f"{len(result['codenames'])} permissions aplicadas ao grupo."
            )
        )
