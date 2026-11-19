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
import os
import re
import subprocess
from collections.abc import Callable
from typing import Any

import pytest
from helpers import BASE_URL
from playwright.sync_api import Page, expect

E2E_USERNAME = "e2e_candidate"
E2E_PASSWORD = "e2e-senha-123"
E2E_TEACHER_USERNAME = "e2e_teacher"
E2E_SECRETARIAT_USERNAME = "e2e_secretariat"
E2E_ADMIN_USERNAME = "e2e_admin"

E2E_USERS = {
    "candidate": (E2E_USERNAME, E2E_PASSWORD),
    "teacher": (E2E_TEACHER_USERNAME, E2E_PASSWORD),
    "secretariat": (E2E_SECRETARIAT_USERNAME, E2E_PASSWORD),
    "admin": (E2E_ADMIN_USERNAME, E2E_PASSWORD),
}

_COMPOSE_PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "sistema_cea_e2e")
_COMPOSE_FILE = os.getenv("E2E_COMPOSE_FILE", "docker-compose.e2e.yml")


def run_manage(*args: str) -> str:
    """Executa ``manage.py`` no serviço web em execução da stack E2E."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            _COMPOSE_PROJECT,
            "-f",
            _COMPOSE_FILE,
            "exec",
            "-T",
            "web",
            "python",
            "manage.py",
            *args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            "Comando falhou:\n"
            f"{' '.join(result.args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result.stdout


def _last_json_line(output: str) -> Any:
    """Extrai a última linha JSON (objeto ou lista) emitida por um comando."""
    for line in reversed(output.splitlines()):
        candidate = line.strip()
        if candidate.startswith(("{", "[")):
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


@pytest.fixture(scope="session")
def created_terms() -> list[int]:
    """Períodos letivos criados pela suíte (removidos ao final, se vazios)."""
    return []


@pytest.fixture(scope="session")
def created_user_emails() -> list[str]:
    """E-mails de usuários criados pela suíte (desativados ao final)."""
    return []


@pytest.fixture(scope="session", autouse=True)
def cleanup_e2e_data(
    seed_database: dict,
    created_protocols: list[str],
    created_terms: list[int],
    created_user_emails: list[str],
) -> object:
    """Remove/soft-deleta os dados criados pela suíte ao final."""
    yield
    args: list[str] = ["e2e_cleanup"]
    for protocol in sorted(set(created_protocols)):
        args.extend(["--protocol", protocol])
    for term_id in sorted(set(created_terms)):
        args.extend(["--term-id", str(term_id)])
    for email in sorted(set(created_user_emails)):
        args.extend(["--deactivate-email", email])
    if len(args) > 1:
        run_manage(*args)


@pytest.fixture
def login_as(page: Page) -> Callable[..., None]:
    """Autentica um usuário E2E por papel (candidate/teacher/secretariat)."""

    def _login(role: str = "candidate") -> None:
        username, password = E2E_USERS[role]
        # Troca de perfil no mesmo teste: limpa a sessão anterior antes do login.
        page.context.clear_cookies()
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


@pytest.fixture
def latest_email() -> Callable[..., dict[str, Any]]:
    """Lê a mensagem mais recente da caixa em arquivo da stack E2E."""

    def _latest(to: str | None = None, subject_contains: str | None = None) -> dict[str, Any]:
        args = ["e2e_mailbox", "--latest", "--json"]
        if to:
            args.extend(["--to", to])
        if subject_contains:
            args.extend(["--subject-contains", subject_contains])
        output = run_manage(*args)
        messages = _last_json_line(output)
        if isinstance(messages, dict):
            messages = [messages]
        assert messages, "Nenhum e-mail encontrado na caixa E2E."
        return messages[0]

    return _latest


@pytest.fixture
def application_state() -> Callable[[str], dict[str, Any]]:
    """Inspeciona o estado persistido de uma inscrição (JSON)."""

    def _state(protocol: str) -> dict[str, Any]:
        output = run_manage("inspect_application", "--protocol", protocol)
        return _last_json_line(output)

    return _state


@pytest.fixture
def create_term(
    created_terms: list[int],
) -> Callable[..., dict[str, Any]]:
    """Cria um período letivo via comando real (dispara o post_save)."""

    def _create(year: int, period: str = "first", **kwargs: str) -> dict[str, Any]:
        args = ["e2e_create_term", "--year", str(year), "--period", period]
        for key, value in kwargs.items():
            args.extend([f"--{key.replace('_', '-')}", value])
        data = _last_json_line(run_manage(*args))
        assert isinstance(data, dict)
        if data.get("created"):
            created_terms.append(int(data["id"]))
        return data

    return _create


@pytest.fixture
def e2e_environment() -> dict[str, Any]:
    """Configuração efetiva do app E2E (gateways, Celery, e-mail)."""
    data = _last_json_line(run_manage("e2e_environment", "--json"))
    assert isinstance(data, dict)
    return data


@pytest.fixture
def manage() -> Callable[..., str]:
    """Executa um comando de management na stack E2E (setup/inspeção)."""

    def _run(*args: str) -> str:
        return run_manage(*args)

    return _run
