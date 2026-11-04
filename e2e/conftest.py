"""Fixtures dos testes E2E de navegador (Playwright).

Os testes rodam contra a aplicação Django em execução (padrão:
http://cea.dev.ime, configurável por ``E2E_BASE_URL``). Os comandos de seed e
de preparação usam o serviço ``web`` declarado em ``docker-compose.e2e.yml``,
que compartilha o banco da aplicação — sem depender de ``docker compose exec``
no projeto principal.

Cada inscrição criada é registrada e, ao fim da sessão, marcada como excluída
via ``manage.py e2e_cleanup`` (exclusão lógica, sem apagar dados).
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable

import pytest
from helpers import BASE_URL
from playwright.sync_api import Page, expect

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
    """Executa um comando ``manage.py`` no serviço web do compose E2E."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.e2e.yml",
            "run",
            "--rm",
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


def _last_json_line(output: str) -> dict:
    """Extrai a última linha JSON emitida por ``seed_e2e``/``simulate_journey``."""
    for line in reversed(output.splitlines()):
        candidate = line.strip()
        if candidate.startswith("{"):
            return json.loads(candidate)
    raise AssertionError(f"Saída JSON não encontrada:\n{output}")


@pytest.fixture(scope="session", autouse=True)
def seed_database() -> dict:
    """Semeia os dados mínimos e devolve o período canônico do E2E."""
    return _last_json_line(run_manage("seed_e2e"))


@pytest.fixture(scope="session")
def seed_term(seed_database: dict) -> dict:
    """Período letivo criado/garantido pelo seed E2E (id/ano/semestre)."""
    return seed_database["term"]


@pytest.fixture(scope="session")
def created_protocols() -> list[str]:
    """Protocolos de inscrições criadas durante a sessão (para cleanup)."""
    return []


@pytest.fixture(scope="session", autouse=True)
def cleanup_e2e_data(
    seed_database: dict, created_protocols: list[str]
) -> object:
    """Marca como excluídas as inscrições criadas pela suíte ao final."""
    yield
    protocols = sorted(set(created_protocols))
    if not protocols:
        return
    args: list[str] = ["e2e_cleanup"]
    for protocol in protocols:
        args.extend(["--protocol", protocol])
    run_manage(*args)


@pytest.fixture
def login_as(page: Page) -> Callable[..., None]:
    """Autentica um usuário E2E por papel (candidate/teacher/secretariat)."""

    def _login(role: str = "candidate") -> None:
        username, password = E2E_USERS[role]
        page.goto(f"{BASE_URL}/auth/login/")
        page.fill("#id_username", username)
        page.fill("#id_password", password)
        page.click("button[type='submit']")
        expect(page).not_to_have_url(re.compile(r".*/auth/login/?$"))
        expect(page.locator("h1.page-title")).to_be_visible()

    return _login


@pytest.fixture
def login(login_as: Callable[..., None]) -> Callable[..., None]:
    """Atalho retrocompatível: autentica o candidato E2E."""

    def _login() -> None:
        login_as("candidate")

    return _login


@pytest.fixture
def create_application(
    created_protocols: list[str],
) -> Callable[..., str]:
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
            "--json",
        )
        protocol = _last_json_line(output)["protocol"]
        created_protocols.append(protocol)
        return protocol

    return _create


@pytest.fixture
def track_protocol(created_protocols: list[str]) -> Callable[[str], None]:
    """Registra um protocolo criado pela UI para o cleanup da sessão."""

    def _track(protocol: str) -> None:
        created_protocols.append(protocol)

    return _track
