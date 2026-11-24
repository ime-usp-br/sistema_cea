"""E2E das validações de formulário (TS-VAL-001..007)."""

from __future__ import annotations

import re

from helpers import (
    BASE_URL,
    fill_valid_project,
    set_application_term,
)
from playwright.sync_api import Page, expect


def _open_valid_project(page: Page, login, term_id: int | str) -> None:
    login()
    page.goto(f"{BASE_URL}/inscricoes/nova/")
    expect(page.locator("#form-inscricao")).to_be_visible()
    set_application_term(page, term_id)
    fill_valid_project(page)


def _assert_form_error(page: Page, text: str) -> None:
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r".*/inscricoes/nova/$"))
    expect(page.locator("body")).to_contain_text(text)


# Cobre: TS-VAL-001
def test_E2E_VAL_001_telefone_invalido_e_rejeitado(
    page: Page, login, e2e_term
) -> None:
    _open_valid_project(page, login, e2e_term["id"])
    page.fill('input[name="contact_phone"]', "119999")
    _assert_form_error(page, "telefone")


# Cobre: TS-VAL-002
def test_E2E_VAL_002_whatsapp_exige_celular(page: Page, login, e2e_term) -> None:
    _open_valid_project(page, login, e2e_term["id"])
    page.fill('input[name="contact_phone"]', "(11) 3333-4444")
    page.check('input[name="has_whatsapp"]')
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r".*/inscricoes/nova/$"))
    expect(page.locator("body")).to_contain_text(re.compile("celular|WhatsApp"))


# Cobre: TS-VAL-003
def test_E2E_VAL_003_nome_com_numero_ou_incompleto_e_rejeitado(
    page: Page, login, e2e_term
) -> None:
    _open_valid_project(page, login, e2e_term["id"])
    page.fill('input[name="researcher_name"]', "João 123")
    _assert_form_error(page, "nome")

    page.fill('input[name="researcher_name"]', "João")
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r".*/inscricoes/nova/$"))
    expect(page.locator("body")).to_contain_text("completo")


# Cobre: TS-VAL-004
def test_E2E_VAL_004_confirmacao_de_email_obrigatoria(
    page: Page, login, e2e_term
) -> None:
    _open_valid_project(page, login, e2e_term["id"])
    page.fill('input[name="contact_email_confirmation"]', "")
    _assert_form_error(page, "Confirme o e-mail")

    page.fill('input[name="contact_email_confirmation"]', "outro@example.com")
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r".*/inscricoes/nova/$"))
    expect(page.locator("body")).to_contain_text("não conferem")


def _fill_receipt(page: Page) -> None:
    page.check('input[name="wants_refund_receipt"][value="true"]')
    page.fill('input[name="refund_account_holder_name"]', "Maria da Silva")
    page.fill('input[name="refund_account_holder_tax_id"]', "11144477735")
    page.fill('input[name="refund_bank_name"]', "Banco do Brasil")
    page.fill('input[name="refund_branch_number"]', "1234")
    page.fill('input[name="refund_bank_account_number"]', "56789")
    page.check('input[name="refund_bank_account_type"][value="checking"]')
    page.fill('textarea[name="refund_receipt_details"]', "Nome e CPF")


# Cobre: TS-VAL-005
def test_E2E_VAL_005_agencia_e_conta_so_numeros(
    page: Page, login, e2e_term
) -> None:
    _open_valid_project(page, login, e2e_term["id"])
    _fill_receipt(page)
    page.fill('input[name="refund_branch_number"]', "12A3")
    _assert_form_error(page, "agência")


# Cobre: TS-VAL-006
def test_E2E_VAL_006_recibo_e_banco_invalidos(
    page: Page, login, e2e_term
) -> None:
    _open_valid_project(page, login, e2e_term["id"])
    _fill_receipt(page)
    page.fill('textarea[name="refund_receipt_details"]', "---")
    _assert_form_error(page, "recibo")

    page.fill('textarea[name="refund_receipt_details"]', "Nome e CPF")
    page.fill('input[name="refund_bank_name"]', "123")
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r".*/inscricoes/nova/$"))
    expect(page.locator("body")).to_contain_text("banco")


# Cobre: TS-VAL-007
def test_E2E_VAL_007_projeto_fora_do_periodo_mostra_erro(
    page: Page, login, create_term
) -> None:
    closed_term = create_term(
        9200,
        submission_start="2020-01-01",
        submission_end="2020-12-31",
    )
    login()
    page.goto(f"{BASE_URL}/inscricoes/nova/")
    expect(page.locator("#form-inscricao")).to_be_visible()
    set_application_term(page, closed_term["id"])
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r".*/inscricoes/nova/$"))
    expect(page.locator("body")).to_contain_text(
        "Inscrições para Projetos indisponíveis neste período."
    )
