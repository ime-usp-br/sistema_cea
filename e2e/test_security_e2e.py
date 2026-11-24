"""E2E de isolamento por perfil: candidato só acessa a própria inscrição e o
docente não vê dados financeiros/CPF na ficha."""

from __future__ import annotations

import uuid

import pytest
from helpers import (
    BASE_URL,
    create_consultation_via_ui,
    create_project_via_ui,
    extract_link,
    pay_fee,
    submit_dataset_file,
    wait_for_page,
)
from playwright.sync_api import Page, expect

PASSWORD = "senha-forte-123"


def _create_second_candidate(page: Page, latest_email, created_user_emails: list[str]) -> str:
    email = f"e2e.outro.{uuid.uuid4().hex[:8]}@example.com"
    created_user_emails.append(email)
    # O teste anterior autenticou o dono da inscrição; o cadastro/verificação
    # do segundo candidato precisa começar sem sessão.
    page.context.clear_cookies()
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


# Cobre: TS-APP-001, TS-SEC-003
@pytest.mark.p0
def test_E2E_SEC_001_candidato_nao_acessa_inscricao_de_terceiro(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    latest_email,
    created_user_emails,
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
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


# Cobre: TS-SEC-004
def test_E2E_SEC_002_docente_nao_ve_cpf_nem_financeiro(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    submit_dataset_file(page, protocol)
    login_as("teacher")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    body = page.locator("body")
    expect(body).not_to_contain_text("Financeiro")
    expect(body).not_to_contain_text("CPF/CNPJ")


# Cobre: TS-SEC-004
def test_E2E_SEC_003_secretaria_ve_financeiro_e_cpf(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    submit_dataset_file(page, protocol)
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    expect(page.locator("body")).to_contain_text("Financeiro")
    expect(page.locator("body")).to_contain_text("CPF/CNPJ")


# Cobre: TS-SEC-006
def test_E2E_SEC_006_login_rate_limit(page: Page) -> None:
    username = f"e2e.rate.{uuid.uuid4().hex[:8]}@example.com"
    page.goto(f"{BASE_URL}/auth/login/")
    for _ in range(5):
        page.fill("#id_username", username)
        page.fill("#id_password", "senha-errada")
        page.click("button[type='submit']")
        expect(page.locator("#id_username")).to_be_visible()

    page.fill("#id_username", username)
    page.fill("#id_password", "senha-errada")
    page.click("button[type='submit']")
    expect(page.locator("body")).to_contain_text("Muitas tentativas")


# Cobre: TS-SEC-001
def test_E2E_SEC_001_post_sem_csrf_e_rejeitado(page: Page, login) -> None:
    page.goto(f"{BASE_URL}/auth/login/")
    anonymous = page.request.post(
        f"{BASE_URL}/auth/login/",
        form={"username": "sem-csrf@example.com", "password": "x"},
    )
    assert anonymous.status == 403

    login()
    authenticated = page.request.post(
        f"{BASE_URL}/inscricoes/nova/",
        form={"researcher_name": "Sem CSRF"},
    )
    assert authenticated.status == 403
