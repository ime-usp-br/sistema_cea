"""E2E dos processos restantes: ambiente hermético, mudança de modalidade,
geração/regeneração administrativa de boleto, sincronização do relatório,
recibos e resgate de inscrição importada."""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

import pytest
from helpers import (
    BASE_URL,
    create_consultation_via_ui,
    create_project_via_ui,
    pay_fee,
    review_submission_by_protocol,
    schedule_screening_for,
    start_payment,
    submit_dataset_external_link,
    submit_dataset_file,
    wait_for_page,
)
from playwright.sync_api import Page, expect


def test_E2E_ENV_001_stack_sem_gateways_externos(e2e_environment: dict) -> None:
    assert e2e_environment["debug"] is True
    assert e2e_environment["payment_gateway_fake"] is True
    assert e2e_environment["pix_gateway"] == "FakePixGateway"
    assert e2e_environment["bank_slip_gateway"] == "FakeBankSlipGateway"
    assert e2e_environment["celery_task_always_eager"] is True
    assert "filebased" in e2e_environment["email_backend"]


# Cobre: TS-MOD-004, TS-MOD-005
def test_E2E_MOD_004_005_mudanca_de_modalidade_pela_lista(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    login_as("secretariat")

    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    row.locator("button:has-text('Mudar')").click()
    wait_for_page(page)
    state = application_state(protocol)
    assert state["modality"] == "project"
    assert state["lifecycle_status"] == "awaiting_payment"
    project_fee = next(fee for fee in state["fees"] if fee["type"] == "application_fee")
    assert project_fee["amount"] == "80.00"

    # Converte de volta para Consulta (substitui a taxa não paga por R$ 140).
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    row.locator("button:has-text('Mudar')").click()
    wait_for_page(page)
    state = application_state(protocol)
    assert state["modality"] == "consultation"
    consultation_fee = next(
        fee for fee in state["fees"] if fee["type"] == "application_fee"
    )
    assert consultation_fee["amount"] == "140.00"


# Cobre: TS-BSL-001, TS-BSL-007
def test_E2E_BSL_ADMIN_001_gerar_e_regenerar_boleto_pela_secretaria(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    page.once("dialog", lambda dialog: dialog.accept())
    row.locator("button:has-text('Gerar Boleto (Manual)')").click()
    wait_for_page(page)

    state = application_state(protocol)
    slip = next(
        instrument
        for fee in state["fees"]
        for instrument in fee["instruments"]
        if instrument["method"] == "bank_slip"
    )
    first_reference = slip["bank_slip_reference"]

    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    page.click("button:has-text('Regenerar boleto')")
    wait_for_page(page)
    state = application_state(protocol)
    references = [
        instrument["bank_slip_reference"]
        for fee in state["fees"]
        for instrument in fee["instruments"]
        if instrument["method"] == "bank_slip"
    ]
    assert first_reference in references
    assert any(reference != first_reference for reference in references)


# Cobre: TS-REP-002
def test_E2E_REP_002_sincronizacao_do_relatorio_usa_gateway_simulado(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "boleto")
    login_as("secretariat")
    page.goto(f"{BASE_URL}/gestao/relatorios/financeiro/?term=all")
    wait_for_page(page, "Relatório Financeiro")
    row = page.locator("tr", has_text=protocol).first
    with page.expect_response(lambda response: "/sincronizar/" in response.url) as info:
        row.locator("button:has-text('Sincronizar')").click()
    response = info.value
    assert response.status == 200
    assert response.url.endswith(f"/gestao/relatorios/financeiro/{protocol}/sincronizar/")
    assert "json" in (response.header_value("content-type") or "")


# Cobre: TS-AUD-018, TS-FILE-002
def test_E2E_DOC_002_recibo_de_pagamento_e_resumo_da_triagem(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
) -> None:
    # Recibo após pagamento.
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    receipt_link = page.locator("a:has-text('Recibo')").first.get_attribute("href")
    receipt = page.request.get(f"{BASE_URL}{receipt_link}")
    assert receipt.status == 200 and receipt.body().startswith(b"%PDF")

    # Resumo da triagem.
    project = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, project, "pix")
    submit_dataset_file(page, project)
    login_as("teacher")
    review_submission_by_protocol(page, project, "approved", "Dados adequados.")
    login_as("secretariat")
    schedule_screening_for(
        page, project, (date.today() - timedelta(days=1)).isoformat()
    )
    page.goto(f"{BASE_URL}/triagens/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=project).first
    row.locator("a[title='Informar Resultado']").click()
    wait_for_page(page)
    summary_link = page.locator("a:has-text('Resumo (PDF)')").get_attribute("href")
    summary = page.request.get(f"{BASE_URL}{summary_link}")
    assert summary.status == 200 and summary.body().startswith(b"%PDF")


# Cobre: TS-CLAIM-001, TS-CLAIM-002, TS-CLAIM-003, TS-EVT-004
@pytest.mark.p0
def test_E2E_CLAIM_001_002_003_resgate_por_codigo_do_email(
    page: Page,
    login,
    latest_email,
    application_state,
    manage,
    candidate_account,
    track_protocol,
) -> None:
    protocol = f"{uuid.uuid4().int % 1_000_000_000:09d}"
    contact_email = candidate_account["email"]
    manage(
        "e2e_create_imported_application",
        "--protocol",
        protocol,
        "--contact-email",
        contact_email,
    )
    track_protocol(protocol)
    login()
    page.goto(f"{BASE_URL}/vincular-inscricao/")
    wait_for_page(page)
    page.fill('input[name="protocol"]', protocol)
    page.fill('input[name="contact_email_or_tax_id"]', contact_email)
    page.click("button:has-text('Enviar código')")
    wait_for_page(page)

    message = latest_email(to=contact_email)
    match = re.search(r"código de resgate é:\s*(\d{6})", message["body"])
    assert match is not None, message["body"]
    page.fill('input[name="code"]', match.group(1))
    page.click("button:has-text('Confirmar')")
    wait_for_page(page)

    state = application_state(protocol)
    assert state["owner"] == candidate_account["username"]
    assert "claim.verified" in {event["code"] for event in state["events"]}


# Cobre: TS-FILE-001, TS-FILE-003, TS-FILE-006
def test_E2E_FILE_001_003_006_metadados_e_download_nao_autorizado(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    submit_dataset_file(page, protocol)
    submission = application_state(protocol)["audit_submissions"][-1]
    assert submission["has_file"] is True
    assert submission["file"]["purpose"] == "dataset_submission"
    assert submission["file"]["filename"] == "dados-e2e.csv"
    assert submission["file"]["size"] > 0
    assert submission["file"]["checksum"]

    unauthorized = page.request.get(
        f"{BASE_URL}/auditoria/submissao/{submission['id']}/arquivo/"
    )
    assert unauthorized.status == 403

    link_protocol = create_project_via_ui(
        page, login, track_protocol, e2e_term["id"]
    )
    pay_fee(page, link_protocol, "pix")
    submit_dataset_external_link(page, link_protocol)
    link_submission = application_state(link_protocol)["audit_submissions"][-1]
    assert link_submission["channel"] == "external_link"
    assert link_submission["has_file"] is False
    assert link_submission["file"] is None
    assert link_submission["external_url"] == "https://example.com/dados-e2e"


# Cobre: TS-CLAIM-004, TS-CLAIM-006
def test_E2E_CLAIM_004_006_codigo_incorreto_nao_vincula(
    page: Page,
    login,
    latest_email,
    application_state,
    manage,
    candidate_account,
    track_protocol,
) -> None:
    protocol = f"{uuid.uuid4().int % 1_000_000_000:09d}"
    contact_email = candidate_account["email"]
    manage(
        "e2e_create_imported_application",
        "--protocol",
        protocol,
        "--contact-email",
        contact_email,
    )
    track_protocol(protocol)

    login()
    page.goto(f"{BASE_URL}/vincular-inscricao/")
    wait_for_page(page)
    page.fill('input[name="protocol"]', protocol)
    page.fill('input[name="contact_email_or_tax_id"]', contact_email)
    page.click("button:has-text('Enviar código')")
    wait_for_page(page)

    # TS-CLAIM-006: solicitar o código não vincula silenciosamente.
    assert application_state(protocol)["owner"] is None

    message = latest_email(to=contact_email)
    match = re.search(r"código de resgate é:\s*(\d{6})", message["body"])
    assert match is not None, message["body"]
    correct_code = match.group(1)
    wrong_code = "000000" if correct_code != "000000" else "111111"

    page.fill('input[name="code"]', wrong_code)
    with page.expect_response(
        lambda response: "/vincular-inscricao/confirmar/" in response.url
    ) as response_info:
        page.click("button:has-text('Confirmar')")
    assert response_info.value.status == 400

    state = application_state(protocol)
    assert state["owner"] is None
    assert "claim.verification_failed" in {
        event["code"] for event in state["events"]
    }


def _change_modality(page: Page, protocol: str) -> None:
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    row.locator("button:has-text('Mudar')").click()
    wait_for_page(page)


# Cobre: TS-MOD-001
def test_E2E_MOD_001_projeto_nao_pago_convertido_em_consulta(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    login_as("secretariat")
    _change_modality(page, protocol)
    state = application_state(protocol)
    assert state["modality"] == "consultation"
    fee = next(item for item in state["fees"] if item["type"] == "application_fee")
    assert fee["amount"] == "140.00"


# Cobre: TS-MOD-002
def test_E2E_MOD_002_projeto_pago_convertido_em_consulta(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    login_as("secretariat")
    _change_modality(page, protocol)
    state = application_state(protocol)
    assert state["modality"] == "consultation"
    supplement = next(item for item in state["fees"] if item["type"] == "supplement_fee")
    assert supplement["amount"] == "60.00"
    app_fee = next(item for item in state["fees"] if item["type"] == "application_fee")
    assert app_fee["is_paid"] is True


# Cobre: TS-REF-005
def test_E2E_REF_005_reembolso_acima_do_pago_e_rejeitado(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    page.goto(f"{BASE_URL}/reembolsos/inscricao/{protocol}/solicitar/")
    wait_for_page(page)
    page.fill('input[name="amount"]', "999.00")
    page.fill('textarea[name="reason"]', "Acima do pago.")
    with page.expect_response(
        lambda response: response.request.method == "POST"
    ) as response_info:
        page.click("button[type='submit']")
    assert response_info.value.status == 400
    expect(page.locator("body")).to_contain_text("não pode exceder")
    assert application_state(protocol)["refunds"] == []
