"""Cria um candidato isolado para os testes E2E.

Usado pelas fixtures para que cada teste tenha seu próprio candidato sem
depender do usuário fixo do ``seed_e2e``. O comando nunca reutiliza nem
promove uma conta existente: se username ou e-mail já existirem, ele falha.
"""

from __future__ import annotations

import json
import re
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Cria um candidato E2E isolado e emite JSON (somente DEBUG)."

    DEFAULT_PASSWORD = "e2e-senha-123"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--suffix",
            required=True,
            help="Sufixo único para username/e-mail (ex.: run-teste).",
        )
        parser.add_argument("--password", default=self.DEFAULT_PASSWORD)
        parser.add_argument(
            "--inactive",
            action="store_true",
            help="Cria a conta já desativada (para TS-AUTH-007).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from users.models import User

        if not settings.DEBUG:
            raise CommandError("e2e_create_user exige DEBUG=True.")

        suffix = re.sub(r"[^a-z0-9]+", "-", options["suffix"].lower()).strip("-")
        if not suffix:
            raise CommandError("--suffix precisa conter letras ou números.")
        username = f"e2e_candidate_{suffix}"[:150]
        email = f"e2e.candidate.{suffix}@example.com"[:254]

        if User.objects.filter(username=username).exists():
            raise CommandError(f"Já existe um usuário com o username {username}.")
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Já existe um usuário com o e-mail {email}.")

        user = User(
            username=username,
            email=email,
            full_name=f"E2E candidate {suffix}",
            role=User.Role.CANDIDATE,
            is_active=not options["inactive"],
            is_email_verified=True,
            is_staff=False,
            is_superuser=False,
        )
        user.set_password(options["password"])
        try:
            user.save()
        except IntegrityError as exc:
            raise CommandError(
                "Não foi possível criar o usuário E2E (username/e-mail duplicado)."
            ) from exc

        self.stdout.write(
            json.dumps(
                {
                    "id": user.pk,
                    "username": user.username,
                    "email": user.email,
                    "password": options["password"],
                    "role": user.role,
                    "created": True,
                }
            )
        )
