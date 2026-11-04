"""Testes E2E de navegador por jornada (Playwright + pytest).

Cobrem o happy path de pagamento (incluindo a Taxa de Projeto pela UI — D3),
reembolso do candidato, transferência pendente e telas de backoffice.
As pré-condições complexas são montadas via ``simulate_journey`` (serviços
reais), deixando a navegação para os pontos que o E2E deve validar.
"""

from __future__ import annotations

import re
import uuid

from helpers import BASE_URL, pay_fee
from playwright.sync_api import Page, expect


def _detail(page: Page) -> None:
    expect(page.locator("h1.page-title")).to_be_visible()


def test_E2E_N3_01_pagar_taxa_de_inscricao_por_pix(login, create_application, page: Page) -> None:
    protocol = create_application("project")
    login()
    pay_fee(page, protocol, method="pix")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Aguardando envio de dados")


def test_E2E_N3_04_projeto_paga_taxa_de_projeto_pela_ui(
    login, create_application, page: Page
) -> None:
    protocol = create_application(
        "project",
        "--pay",
        "--submit-dataset",
        "--review",
        "approved",
        "--schedule-screening",
        "--screening-feedback",
        "screening_completed",
        "--screening-decision",
        "approved_as_project",
    )
    login()
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    # D3: a ficha do candidato expõe o pagamento da Taxa de Projeto.
    expect(page.locator("body")).to_contain_text("Aguardando pagamento")

    pay_fee(page, protocol, method="pix")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Aprovado como Projeto")


def test_E2E_N7_01_candidato_solicita_reembolso_sem_403(
    login, create_application, page: Page
) -> None:
    protocol = create_application("consultation", "--pay")
    login()
    page.goto(f"{BASE_URL}/reembolsos/inscricao/{protocol}/solicitar/")
    _detail(page)
    page.fill('input[name="amount"]', "100.00")
    page.fill('textarea[name="reason"]', "Desistência E2E.")
    page.click("button[type='submit']")
    _detail(page)
    expect(page).to_have_url(re.compile(rf".*/inscricoes/{protocol}/$"))
    expect(page.locator("body")).to_contain_text("Desistência E2E.")


def test_E2E_N9_02_transferir_semestre_nao_quebra(
    login_as, create_application, page: Page
) -> None:
    protocol = create_application("project")
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Transferir semestre')")
    _detail(page)
    # O seed garante um período posterior (dinâmico): a transferência conclui sem 500.
    expect(page).to_have_url(re.compile(rf".*/inscricoes/{protocol}/$"))
    expect(page.locator("body")).to_contain_text("term.transferred")


def test_E2E_N9_03_backoffice_lista_e_relatorio(
    login_as, create_application, seed_term, page: Page
) -> None:
    protocol = create_application("consultation")
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Inscri")
    expect(page.locator("body")).to_contain_text(protocol)
    expect(page.locator("body")).to_contain_text(str(seed_term["year"]))

    page.goto(f"{BASE_URL}/gestao/relatorios/financeiro/?term=all")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Relatório Financeiro")
    expect(page.locator("body")).to_contain_text("Taxa de Projeto")
    expect(page.locator("body")).to_contain_text(protocol)
    expect(page.locator("body")).to_contain_text("R$ 140,00")


def test_E2E_N1_02_cadastro_bloqueia_login_ate_confirmar(page: Page) -> None:
    page.goto(f"{BASE_URL}/cadastro/")
    _detail(page)
    email = f"e2e.cadastro.{uuid.uuid4().hex[:8]}@example.com"
    page.fill('input[name="full_name"]', "Cadastro E2E")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password1"]', "senha-forte-123")
    page.fill('input[name="password2"]', "senha-forte-123")
    page.click("button[type='submit']")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Confirme seu e-mail")

    page.goto(f"{BASE_URL}/auth/login/")
    page.fill("#id_username", email)
    page.fill("#id_password", "senha-forte-123")
    page.click("button[type='submit']")
    # A página de login usa <h2>; espera pela mensagem de bloqueio, não pelo título.
    expect(page.locator("body")).to_contain_text("Confirme seu e-mail")


def test_E2E_N1_03_recuperacao_de_senha_abre(page: Page) -> None:
    page.goto(f"{BASE_URL}/auth/password_reset/")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Recuperar senha")
