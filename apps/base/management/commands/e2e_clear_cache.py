"""Limpa o cache da stack E2E (contadores de rate limit)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Limpa o cache da stack E2E (somente DEBUG)."

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("e2e_clear_cache exige DEBUG=True.")
        cache.clear()
        self.stdout.write(self.style.SUCCESS("Cache E2E limpo."))
