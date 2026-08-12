"""Fixtures dos testes E2E de navegador (Playwright).

Os testes rodam contra a aplicação Django em execução no container Docker
(http://localhost:8000), por isso precisam de dados pré-existentes no banco de
desenvolvimento. O fixture de sessão ``seed_database`` garante que um candidato
com credenciais conhecidas e um período letivo existam, de forma idempotente,
antes de qualquer cenário rodar.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

import pytest
from helpers import BASE_URL
from playwright.sync_api import Page

E2E_USERNAME = "e2e_candidate"
E2E_PASSWORD = "e2e-senha-123"


@pytest.fixture(scope="session", autouse=True)
def seed_database() -> None:
    """Semeia os dados mínimos (candidato + período) no banco de DEV do container."""
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "web",
            "python",
            "manage.py",
            "seed_e2e",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def login(page: Page) -> Callable[..., None]:
    """Autentica o candidato E2E via login local e aguarda o redirect."""
    def _login(username: str = E2E_USERNAME, password: str = E2E_PASSWORD) -> None:
        page.goto(f"{BASE_URL}/auth/login/")
        page.fill("#id_username", username)
        page.fill("#id_password", password)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

    return _login
