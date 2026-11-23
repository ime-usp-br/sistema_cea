"""E2E de contas do candidato externo (sem Senha Única).

O e-mail é "desviado" para o backend de arquivo da stack E2E; os testes leem a
mensagem pelo comando ``e2e_mailbox`` e seguem o link real enviado ao
candidato (confirmação de e-mail e recuperação de senha).
"""

from __future__ import annotations

import re
import uuid

from helpers import BASE_URL, extract_link
from playwright.sync_api import Page, expect

PASSWORD = "senha-forte-123"


def _new_email() -> str:
    return f"e2e.conta.{uuid.uuid4().hex[:8]}@example.com"


def _signup(page: Page, email: str, full_name: str = "Conta E2E") -> None:
    page.goto(f"{BASE_URL}/cadastro/")
    page.fill('input[name="full_name"]', full_name)
    page.fill('input[name="email"]', email)
    page.fill('input[name="password1"]', PASSWORD)
    page.fill('input[name="password2"]', PASSWORD)
    page.click("button[type='submit']")
    expect(page.locator("body")).to_contain_text("Confirme seu e-mail")


def _login(page: Page, email: str, password: str = PASSWORD) -> None:
    page.goto(f"{BASE_URL}/auth/login/")
    page.fill("#id_username", email)
    page.fill("#id_password", password)
    page.click("button[type='submit']")


# Cobre: TS-AUTH-001
def test_E2E_AUTH_001_area_autenticada_exige_login(page: Page) -> None:
    # A home é uma landing page pública; as rotas de inscrição/painel exigem login.
    page.goto(f"{BASE_URL}/")
    expect(page.locator("body")).to_contain_text("Acessar o sistema")
    page.goto(f"{BASE_URL}/painel/")
    expect(page).to_have_url(re.compile(r".*/auth/login/.*"))


# Cobre: TS-AUTH-002, TS-AUTH-003
def test_E2E_AUTH_003_cadastro_externo_confirma_email_e_loga(
    page: Page, latest_email, created_user_emails: list[str]
) -> None:
    email = _new_email()
    created_user_emails.append(email)
    _signup(page, email)

    # Antes de confirmar, o login local é recusado com mensagem clara.
    _login(page, email)
    expect(page.locator("body")).to_contain_text("Confirme seu e-mail")

    # O e-mail foi desviado para a caixa de teste e contém o link real.
    message = latest_email(to=email)
    assert message["to"] == email
    link = extract_link(message["body"], "/verificar-email/")
    page.goto(link)
    expect(page.locator("body")).to_contain_text("E-mail confirmado com sucesso")

    _login(page, email)
    expect(page.locator("h1.page-title")).to_be_visible()
    expect(page.locator("body")).to_contain_text("Painel")


# Cobre: TS-AUTH-002, TS-AUTH-003
def test_E2E_AUTH_003b_reenvio_de_confirmacao_envia_novo_link(
    page: Page, latest_email, created_user_emails: list[str]
) -> None:
    email = _new_email()
    created_user_emails.append(email)
    _signup(page, email)
    first_link = extract_link(latest_email(to=email)["body"], "/verificar-email/")

    page.goto(f"{BASE_URL}/verificar-email/reenviar/")
    page.fill('input[name="email"]', email)
    page.click("button[type='submit']")
    expect(page.locator("body")).to_contain_text("Se existir uma conta pendente")

    second_link = extract_link(latest_email(to=email)["body"], "/verificar-email/")
    assert second_link != first_link

    # O primeiro link foi invalidado pelo reenvio; o segundo funciona.
    page.goto(first_link)
    expect(page.locator("body")).to_contain_text("já foi utilizado")
    page.goto(second_link)
    expect(page.locator("body")).to_contain_text("E-mail confirmado com sucesso")


# Cobre: TS-AUTH-006
def test_E2E_AUTH_006_recuperacao_de_senha_por_email(
    page: Page, latest_email, created_user_emails: list[str]
) -> None:
    email = _new_email()
    created_user_emails.append(email)
    _signup(page, email)
    page.goto(extract_link(latest_email(to=email)["body"], "/verificar-email/"))
    expect(page.locator("body")).to_contain_text("E-mail confirmado com sucesso")

    page.goto(f"{BASE_URL}/auth/password_reset/")
    page.fill('input[name="email"]', email)
    page.click("button[type='submit']")
    expect(page.locator("body")).to_contain_text("enviamos")

    reset_link = extract_link(latest_email(to=email)["body"], "/auth/reset/")
    page.goto(reset_link)
    page.fill('input[name="new_password1"]', "outra-senha-456")
    page.fill('input[name="new_password2"]', "outra-senha-456")
    page.click("button[type='submit']")
    expect(page.locator("body")).to_contain_text("Senha redefinida")

    _login(page, email, "outra-senha-456")
    expect(page.locator("h1.page-title")).to_be_visible()


# Cobre: TS-AUTH-004
def test_E2E_AUTH_004_login_senha_unica_com_faker(page: Page) -> None:
    """Login OAuth1 completo contra o uspdev/senhaunica-faker da stack E2E."""
    page.goto(f"{BASE_URL}/auth/login/")
    page.click("a:has-text('Entrar com Senha Única USP')")

    expect(page).to_have_url(
        re.compile(r"http://senhaunica-faker:3141/wsusuario/oauth/authorize")
    )
    expect(page.locator("#loginUsuario")).to_be_visible()
    # O faker tenta inferir o callback do Referer; fixamos a URL real da aplicação.
    page.fill("#callback", f"{BASE_URL}/callback/")
    page.fill("#loginUsuario", "1600001")
    page.click("button:has-text('Login')")

    expect(page).to_have_url(re.compile(r".*/painel/?$"))
    expect(page.locator("h1.page-title")).to_be_visible()
    expect(page.locator("body")).to_contain_text("Painel")
