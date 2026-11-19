"""E2E de isolamento por perfil: candidato só acessa a própria inscrição e o
docente não vê dados financeiros/CPF na ficha."""

from __future__ import annotations

import uuid

from helpers import BASE_URL, extract_link, wait_for_page
from playwright.sync_api import Page, expect

PASSWORD = "senha-forte-123"


def _create_second_candidate(page: Page, latest_email, created_user_emails: list[str]) -> str:
    email = f"e2e.outro.{uuid.uuid4().hex[:8]}@example.com"
    created_user_emails.append(email)
    page.goto(f"{BASE_URL}/cadastro/")
    page.fill('input[name="full_name"]', "Outro Candidato E2E")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password1"]', PASSWORD)
    page.fill('input[name="password2"]', PASSWORD)
    page.click("button[type='submit']")
    expect(page.locator("body")).to_contain_text("Confirme seu e-mail")
    page.goto(extract_link(latest_email(to=email)["body"], "/verificar-email/"))
    expect(page.locator("body")).to_contain_text("E-mail confirmado com sucesso")
    return email


def test_E2E_SEC_001_candidato_nao_acessa_inscricao_de_terceiro(
    page: Page, login_as, create_application, latest_email, created_user_emails
) -> None:
    protocol = create_application("consultation")
    email = _create_second_candidate(page, latest_email, created_user_emails)

    page.goto(f"{BASE_URL}/auth/login/")
    page.fill("#id_username", email)
    page.fill("#id_password", PASSWORD)
    page.click("button[type='submit']")
    wait_for_page(page)

    detail = page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    assert detail is not None and detail.status == 404
    payment = page.goto(f"{BASE_URL}/pagamento/inscricao/{protocol}/")
    assert payment is not None and payment.status == 404


def test_E2E_SEC_002_docente_nao_ve_cpf_nem_financeiro(
    page: Page, login_as, create_application
) -> None:
    protocol = create_application("project", "--pay", "--submit-dataset")
    login_as("teacher")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    body = page.locator("body")
    expect(body).not_to_contain_text("Financeiro")
    expect(body).not_to_contain_text("CPF/CNPJ")


def test_E2E_SEC_003_secretaria_ve_financeiro_e_cpf(
    page: Page, login_as, create_application
) -> None:
    protocol = create_application("project", "--pay", "--submit-dataset")
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    expect(page.locator("body")).to_contain_text("Financeiro")
    expect(page.locator("body")).to_contain_text("CPF/CNPJ")
