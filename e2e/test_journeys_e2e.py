"""Testes E2E de navegador por jornada (Playwright + pytest).

Cobrem o happy path de pagamento (incluindo a Taxa de Projeto pela UI — D3),
reembolso do candidato, transferência pendente e telas de backoffice.
As inscrições nascem na UI e cada etapa de negócio é executada pelo perfil real.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from helpers import (
    BASE_URL,
    assert_status_page,
    create_consultation_via_ui,
    create_project_via_ui,
    open_first_screening_decision,
    open_teacher_feedback,
    pay_fee,
    register_decision,
    register_feedback,
    review_submission_by_protocol,
    schedule_screening_for,
    submit_dataset_file,
)
from playwright.sync_api import Page, expect


def _detail(page: Page) -> None:
    expect(page.locator("h1.page-title")).to_be_visible()


# Cobre: TS-APP-002, TS-PAY-001, TS-PAY-008
def test_E2E_N3_01_pagar_taxa_de_inscricao_por_pix(
    login, track_protocol, e2e_term, page: Page
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, method="pix")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Aguardando envio de dados")


# Cobre: TS-FEE-001, TS-PAY-009, TS-PAY-012
def test_E2E_N3_04_projeto_paga_taxa_de_projeto_pela_ui(
    login, login_as, track_protocol, application_state, e2e_term, page: Page
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, method="pix")
    assert_status_page(page, protocol, "Aguardando envio de dados")

    submit_dataset_file(page, protocol)
    login_as("teacher")
    review_submission_by_protocol(page, protocol, "approved", "Dados adequados.")
    login_as("secretariat")
    schedule_screening_for(
        page, protocol, (date.today() - timedelta(days=1)).isoformat()
    )
    login_as("teacher")
    open_teacher_feedback(page, "/triagens/", protocol)
    register_feedback(page, "screening_completed")
    login_as("secretariat")
    open_first_screening_decision(page, protocol)
    register_decision(page, "approved_as_project")

    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_payment"
    assert any(fee["type"] == "project_fee" for fee in state["fees"])

    login()
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Aguardando pagamento")
    pay_fee(page, protocol, method="pix")
    assert_status_page(page, protocol, "Aprovado como Projeto")


# Cobre: TS-REF-001
def test_E2E_N7_01_candidato_solicita_reembolso_sem_403(
    login, track_protocol, e2e_term, page: Page
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, method="pix")
    page.goto(f"{BASE_URL}/reembolsos/inscricao/{protocol}/solicitar/")
    _detail(page)
    page.fill('input[name="amount"]', "100.00")
    page.fill('textarea[name="reason"]', "Desistência E2E.")
    page.click("button[type='submit']")
    _detail(page)
    expect(page).to_have_url(re.compile(rf".*/inscricoes/{protocol}/$"))
    expect(page.locator("body")).to_contain_text("Desistência E2E.")


# Cobre: TS-TRM-001, TS-TRM-006
def test_E2E_N9_02_transferir_semestre_nao_quebra(
    login,
    login_as,
    track_protocol,
    e2e_term,
    create_term,
    application_state,
    page: Page,
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    next_term = create_term()
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Transferir semestre')")
    _detail(page)
    expect(page).to_have_url(re.compile(rf".*/inscricoes/{protocol}/$"))
    state = application_state(protocol)
    assert state["term"]["id"] == next_term["id"]
    assert state["transfer_pending"] is False


# Cobre: TS-APP-011, TS-REP-001
def test_E2E_N9_03_backoffice_lista_e_relatorio(
    login, login_as, track_protocol, e2e_term, seed_term, page: Page
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
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


# Cobre: TS-AUTH-002
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


# Cobre: TS-AUTH-006
def test_E2E_N1_03_recuperacao_de_senha_abre(page: Page) -> None:
    page.goto(f"{BASE_URL}/auth/password_reset/")
    _detail(page)
    expect(page.locator("body")).to_contain_text("Recuperar senha")


# Cobre: TS-TRM-005
def test_E2E_TRM_005_transferencia_preserva_pagamentos(
    login,
    login_as,
    track_protocol,
    e2e_term,
    create_term,
    application_state,
    page: Page,
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    before = application_state(protocol)["fees"]
    next_term = create_term()

    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    _detail(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Transferir semestre')")
    _detail(page)

    after_state = application_state(protocol)
    assert after_state["term"]["id"] == next_term["id"]
    assert [
        (fee["id"], fee["type"], fee["amount"], fee["is_paid"]) for fee in after_state["fees"]
    ] == [
        (fee["id"], fee["type"], fee["amount"], fee["is_paid"]) for fee in before
    ]
