"""E2E da auditoria de dados: envio por arquivo/link, correção, aprovação,
rejeição e resolução administrativa."""

from __future__ import annotations

import pytest
from helpers import (
    BASE_URL,
    pay_fee,
    review_submission,
    review_submission_by_protocol,
    wait_for_page,
)
from playwright.sync_api import Page, expect


def _awaiting_review(create_application, modality: str = "project", channel: str = "external_link") -> str:
    flags = ["--pay", "--submit-dataset"]
    if channel == "external_link":
        flags.extend(["--channel", "external_link"])
    return create_application(modality, *flags)


def _resolve_rejected(
    page: Page,
    login_as,
    protocol: str,
    resolution: str,
    target_term: str | None = None,
) -> None:
    login_as("secretariat")
    page.goto(f"{BASE_URL}/auditoria/rejeitadas/")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    row.locator("a:has-text('Decidir')").click()
    wait_for_page(page)
    page.select_option('select[name="resolution"]', resolution)
    if target_term:
        page.select_option('select[name="target_term"]', target_term)
    page.fill('textarea[name="note"]', f"Resolução E2E: {resolution}.")
    page.click("button[type='submit']")
    wait_for_page(page, "Auditorias rejeitadas")


# Cobre: TS-AUD-003, TS-AUD-009, TS-AUD-010, TS-AUD-011
@pytest.mark.p0
def test_E2E_AUD_003_009_010_011_correcao_e_reenvio_ate_aprovacao(
    page: Page, login, login_as, create_application, application_state
) -> None:
    protocol = _awaiting_review(create_application, channel="file")

    login_as("teacher")
    review_submission_by_protocol(page, protocol, "needs_correction", "Corrigir planilha.")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_dataset_correction"

    login()
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    page.click("a:has-text('Corrigir e reenviar dados')")
    wait_for_page(page, "Envio de dados para auditoria")
    page.select_option('select[name="channel"]', "file")
    page.set_input_files('input[name="file"]', {
        "name": "dados-corrigidos.csv",
        "mimeType": "text/csv",
        "buffer": b"coluna_a,coluna_b\n3,4\n",
    })
    page.click("button[type='submit']")
    wait_for_page(page)

    login_as("teacher")
    review_submission_by_protocol(page, protocol, "approved", "Correção aceita.")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_screening_scheduling"
    assert [s["state"] for s in state["audit_submissions"]] == ["needs_correction", "approved"]
    codes = {e["code"] for e in state["events"]}
    assert {"audit.submitted", "audit.reviewed"} <= codes


# Cobre: TS-AUD-005
def test_E2E_AUD_005_envio_por_link_externo_e_fila_docente(
    page: Page, login, login_as, create_application, application_state
) -> None:
    protocol = create_application("project", "--pay")
    login()
    page.goto(f"{BASE_URL}/auditoria/inscricao/{protocol}/enviar/")
    wait_for_page(page)
    page.select_option('select[name="channel"]', "external_link")
    page.fill('input[name="external_url"]', "https://example.com/dados-link-e2e")
    page.check('input[name="external_link_declaration"]')
    page.click("button[type='submit']")
    wait_for_page(page)

    login_as("teacher")
    page.goto(f"{BASE_URL}/auditoria/fila/")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_contain_text("Link externo")
    row.locator("a:has-text('Analisar')").click()
    wait_for_page(page)
    expect(page.locator("body")).to_contain_text("https://example.com/dados-link-e2e")
    review_submission(page, "approved", "Link acessível.")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_screening_scheduling"


# Cobre: TS-AUD-012, TS-AUD-013
def test_E2E_AUD_012_013_rejeicao_e_conversao_em_consulta(
    page: Page, login, login_as, create_application, application_state
) -> None:
    protocol = _awaiting_review(create_application)

    login_as("teacher")
    review_submission_by_protocol(page, protocol, "rejected", "Dados inadequados.")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "dataset_rejected_pending_resolution"

    _resolve_rejected(page, login_as, protocol, "convert_to_consultation")
    state = application_state(protocol)
    assert state["modality"] == "consultation"
    assert state["lifecycle_status"] == "awaiting_payment"
    supplement = next(fee for fee in state["fees"] if fee["type"] == "supplement_fee")
    assert supplement["amount"] == "60.00"

    login()
    pay_fee(page, protocol, method="pix")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_consultation_scheduling"
    assert state["payment_state"] == "paid"


# Cobre: TS-AUD-014
def test_E2E_AUD_014_rejeicao_e_reprovacao(
    page: Page, login_as, create_application, application_state
) -> None:
    protocol = _awaiting_review(create_application)

    login_as("teacher")
    review_submission_by_protocol(page, protocol, "rejected", "Dados inconsistentes.")
    _resolve_rejected(page, login_as, protocol, "reject_application")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "not_approved"


# Cobre: TS-AUD-015, TS-TRM-004
def test_E2E_AUD_015_transferencia_de_periodo(
    page: Page, login_as, create_application, application_state, create_term
) -> None:
    protocol = _awaiting_review(create_application)
    target = create_term(2042, "first")

    login_as("teacher")
    review_submission_by_protocol(page, protocol, "rejected", "Transferir.")
    _resolve_rejected(
        page, login_as, protocol, "transfer_term", target_term=str(target["id"])
    )
    state = application_state(protocol)
    assert state["term"]["id"] == target["id"]
    assert state["audit_submissions"][0]["resolutions"][0]["resolution"] == "transfer_term"
