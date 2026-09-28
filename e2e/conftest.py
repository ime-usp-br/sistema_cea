"""Fixtures dos testes E2E de navegador (Playwright).

Os testes rodam contra a aplicação Django em execução (padrão:
http://cea.dev.ime, configurável por ``E2E_BASE_URL``), por isso precisam de
dados pré-existentes no banco de desenvolvimento. O fixture de sessão
``seed_database`` garante que o período letivo e os usuários
candidato/docente/secretaria existam, de forma idempotente, antes de qualquer
cenário rodar.

Quando a suíte roda **dentro do container e2e** não há acesso ao
``docker compose exec`` usado para semear: nesse caso define-se
``E2E_SKIP_SEED=1`` (feito por ``scripts/run_e2e.sh``, que semeia antes).
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable

import pytest
from helpers import BASE_URL
from playwright.sync_api import Page

E2E_USERNAME = "e2e_candidate"
E2E_PASSWORD = "e2e-senha-123"
E2E_TEACHER_USERNAME = "e2e_teacher"
E2E_SECRETARIAT_USERNAME = "e2e_secretariat"

E2E_USERS = {
    "candidate": (E2E_USERNAME, E2E_PASSWORD),
    "teacher": (E2E_TEACHER_USERNAME, E2E_PASSWORD),
    "secretariat": (E2E_SECRETARIAT_USERNAME, E2E_PASSWORD),
}


def run_manage(*args: str) -> str:
    """Executa um comando ``manage.py`` no container web e devolve o stdout."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "web",
            "python",
            "manage.py",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


@pytest.fixture(scope="session", autouse=True)
def seed_database() -> None:
    """Semeia os dados mínimos (período + 3 usuários) no banco de DEV do container."""
    if os.getenv("E2E_SKIP_SEED") == "1":
        return
    try:
        run_manage("seed_e2e")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
            "Não foi possível semear os dados E2E via `docker compose exec web "
            "python manage.py seed_e2e`. Rode o seed manualmente e use "
            "E2E_SKIP_SEED=1, ou execute ./scripts/run_e2e.sh."
        ) from exc


@pytest.fixture
def login_as(page: Page) -> Callable[..., None]:
    """Autentica um usuário E2E por papel (candidate/teacher/secretariat)."""

    def _login(role: str = "candidate") -> None:
        username, password = E2E_USERS[role]
        page.goto(f"{BASE_URL}/auth/login/")
        page.fill("#id_username", username)
        page.fill("#id_password", password)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

    return _login


@pytest.fixture
def login(login_as: Callable[..., None]) -> Callable[..., None]:
    """Atalho retrocompatível: autentica o candidato E2E."""

    def _login() -> None:
        login_as("candidate")

    return _login


@pytest.fixture
def create_application() -> Callable[..., str]:
    """Cria uma inscrição real para o candidato E2E via ``simulate_journey``.

    Retorna o protocolo de 9 dígitos. Flags extras são repassadas ao comando
    (ex.: ``--pay``, ``--submit-dataset --review approved``).
    """

    def _create(modality: str = "project", *flags: str) -> str:
        output = run_manage(
            "simulate_journey",
            "--submit",
            "--modality",
            modality,
            "--owner",
            E2E_USERNAME,
            *flags,
        )
        match = re.search(r"Inscrição (\d{9})", output)
        if match is None:
            raise AssertionError(f"Protocolo não encontrado na saída:\n{output}")
        return match.group(1)

    return _create
