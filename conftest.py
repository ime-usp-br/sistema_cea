"""Configuração comum dos testes de unidade/integração."""

from __future__ import annotations

import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def _disable_rate_limiting() -> None:
    """Evita que contadores de rate limit vazem entre testes de unidade.

    Os testes específicos de D-03 reativam o limitador com
    ``override_settings(RATE_LIMIT_ENABLED=True, ...)``. A suíte E2E tem
    configuração e contêiner próprios e não carrega este conftest.
    """
    settings.RATE_LIMIT_ENABLED = False
