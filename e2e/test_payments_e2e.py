"""E2E de pagamentos: Pix (webhook/consulta), boleto, manual e reembolso.

Nenhum teste usa rede externa: a stack E2E liga ``PAYMENT_GATEWAY_FAKE`` e a
confirmação de pagamento usa a rota local só-DEBUG ou o webhook real da
aplicação (POST interno).
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from helpers import (
    BASE_URL,
    api_post_json,
    create_consultation_via_ui,
    create_project_via_ui,
    pay_fee,
    simulate_payment,
    start_payment,
    wait_for_page,
)
from playwright.sync_api import Page, expect

WEBHOOK_TOKEN = "dev-webhook-token"


def _fee_amount(state: dict, fee_type: str = "application_fee") -> str:
    value = next(fee["amount"] for fee in state["fees"] if fee["type"] == fee_type)
    return f"{Decimal(value):.2f}".replace(".", ",")


def _pix_reference(state: dict) -> str:
    for fee in state["fees"]:
        for instrument in fee["instruments"]:
            if instrument["method"] == "pix":
                return instrument["pix_reference"]
    raise AssertionError("Pix não encontrado no estado da inscrição.")


# Cobre: TS-PIX-004, TS-PIX-006
@pytest.mark.p0
def test_E2E_PIX_004_webhook_valido_e_idempotente(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "pix")
    state = application_state(protocol)
    reference = _pix_reference(state)
    amount = _fee_amount(state)

    status, body = api_post_json(
        "/webhooks/pix/",
        {"idfpix": reference, "status": "Pago", "valor": amount},
        headers={"X-Token": WEBHOOK_TOKEN},
    )
    assert status == 200 and body.get("processed") is True
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_consultation_scheduling"
    assert state["payment_state"] == "paid"
    assert sum(1 for e in state["events"] if e["code"] == "pix.confirmed") == 1

    # Reentrega do mesmo webhook não duplica pagamento nem confirmação.
    status, _ = api_post_json(
        "/webhooks/pix/",
        {"idfpix": reference, "status": "Pago", "valor": amount},
        headers={"X-Token": WEBHOOK_TOKEN},
    )
    assert status == 200
    state = application_state(protocol)
    assert state["payment_state"] == "paid"
    assert sum(1 for e in state["events"] if e["code"] == "pix.confirmed") == 1


# Cobre: TS-PIX-005, TS-SEC-002
def test_E2E_PIX_005_webhook_com_token_invalido_nao_confirma(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "pix")
    state = application_state(protocol)
    reference = _pix_reference(state)

    status, body = api_post_json(
        "/webhooks/pix/",
        {"idfpix": reference, "status": "Pago", "valor": _fee_amount(state)},
        headers={"X-Token": "token-errado"},
    )
    assert status == 401
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_payment"
    assert any(
        instrument["pix_reference"] == reference and instrument["state"] == "active"
        for fee in state["fees"]
        for instrument in fee["instruments"]
    )


# Cobre: TS-PAY-013, TS-PIX-003, TS-PIX-010
def test_E2E_PIX_003_consulta_de_status_confirma_pagamento(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "pix")
    page.click("button:has-text('Já paguei / verificar pagamento')")
    wait_for_page(page)
    state = application_state(protocol)
    assert state["payment_state"] == "paid"
    assert state["lifecycle_status"] == "awaiting_consultation_scheduling"


# Cobre: TS-BSL-001, TS-BSL-006, TS-BSL-010, TS-PAY-002, TS-PAY-013
@pytest.mark.p0
def test_E2E_BSL_001_boleto_pela_ui_pdf_e_confirmacao(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "boleto")
    state = application_state(protocol)
    slip = next(
        instrument
        for fee in state["fees"]
        for instrument in fee["instruments"]
        if instrument["method"] == "bank_slip"
    )
    assert slip["bank_status"] == "E"
    expect(page.locator("body")).to_contain_text(slip["bank_slip_reference"])

    pdf_link = page.locator("a:has-text('Baixar PDF do boleto')").get_attribute("href")
    response = page.request.get(f"{BASE_URL}{pdf_link}")
    assert response.status == 200
    assert response.body().startswith(b"%PDF")

    simulate_payment(page)
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_dataset_submission"
    paid = next(
        instrument
        for fee in state["fees"]
        for instrument in fee["instruments"]
        if instrument["method"] == "bank_slip"
    )
    assert paid["state"] == "paid"


# Cobre: TS-MAN-001
@pytest.mark.p0
def test_E2E_MAN_001_secretaria_confirma_pagamento_manual_de_boleto_vencido(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    manage,
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "boleto")
    manage("e2e_backdate_bank_slip", "--protocol", protocol)

    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("a:has-text('Confirmar Pagamento (Depósito)')")
    wait_for_page(page, "Confirmar pagamento manual")
    page.fill('textarea[name="note"]', "Depósito identificado no extrato.")
    page.click("button:has-text('Confirmar pagamento')")
    wait_for_page(page, "Confirmar pagamento manual")

    state = application_state(protocol)
    assert state["payment_state"] == "paid"
    assert state["lifecycle_status"] == "awaiting_consultation_scheduling"
    assert "payment.manual_confirmed" in {e["code"] for e in state["events"]}


# Cobre: TS-PAY-014, TS-PAY-019, TS-PAY-020
def test_E2E_PAY_014_cobranca_em_massa_de_boleto_vencido(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    manage,
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "boleto")
    manage("e2e_backdate_bank_slip", "--protocol", protocol)

    login_as("secretariat")
    page.goto(f"{BASE_URL}/cobrancas/vencidos/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    row.locator("input[name='slip_ids']").check()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Enviar e-mail de cobrança')")
    wait_for_page(page)

    state = application_state(protocol)
    assert sum(
        1 for event in state["events"] if event["code"] == "payment.overdue_reminder_sent"
    ) == 1


# Cobre: TS-EVT-003, TS-REF-001, TS-REF-002, TS-REF-003
def test_E2E_REF_001_002_003_reembolso_completo_pela_ui(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    page.goto(f"{BASE_URL}/reembolsos/inscricao/{protocol}/solicitar/")
    wait_for_page(page)
    page.fill('input[name="amount"]', "100.00")
    page.fill('textarea[name="reason"]', "Desistência E2E completa.")
    page.click("button[type='submit']")
    wait_for_page(page)

    state = application_state(protocol)
    assert state["refunds"][0]["status"] == "requested"

    login_as("secretariat")
    page.goto(f"{BASE_URL}/reembolsos/")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    row.locator("a:has-text('Aprovar')").click()
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    row.locator("a:has-text('Executar')").click()
    wait_for_page(page)

    state = application_state(protocol)
    assert state["refunds"][0]["status"] == "executed"
    assert state["payment_state"] == "refunded"
    assert "refund.requested" in {e["code"] for e in state["events"]}


def _fee_instruments(state: dict, fee_type: str = "application_fee") -> list[dict]:
    fee = next(item for item in state["fees"] if item["type"] == fee_type)
    return list(fee["instruments"])


# Cobre: TS-PAY-003, TS-PAY-004, TS-PAY-005
def test_E2E_PAY_003_004_005_troca_de_instrumento_mantem_um_ativo(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "pix")
    instruments = _fee_instruments(application_state(protocol))
    assert [item["method"] for item in instruments if item["state"] == "active"] == [
        "pix"
    ]

    start_payment(page, protocol, "boleto")
    instruments = _fee_instruments(application_state(protocol))
    assert [item["method"] for item in instruments if item["state"] == "active"] == [
        "bank_slip"
    ]
    assert any(
        item["method"] == "pix" and item["state"] == "superseded"
        for item in instruments
    )

    start_payment(page, protocol, "pix")
    instruments = _fee_instruments(application_state(protocol))
    assert [item["method"] for item in instruments if item["state"] == "active"] == [
        "pix"
    ]
    assert any(
        item["method"] == "bank_slip" and item["state"] == "superseded"
        for item in instruments
    )


# Cobre: TS-PAY-006
def test_E2E_PAY_006_taxa_paga_nao_aceita_novo_instrumento(
    page: Page, login, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    before = _fee_instruments(application_state(protocol))
    assert len([item for item in before if item["state"] == "paid"]) == 1

    page.goto(f"{BASE_URL}/pagamento/inscricao/{protocol}/")
    wait_for_page(page, "Pagamento")
    assert page.locator('select[name="method"]').count() == 0
    after = _fee_instruments(application_state(protocol))
    assert len(after) == len(before)


# Cobre: TS-PAY-007
def test_E2E_PAY_007_pix_expirado_permite_nova_geracao(
    page: Page, login, track_protocol, e2e_term, application_state, manage
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    start_payment(page, protocol, "pix")
    assert manage("e2e_expire_pix", "--protocol", protocol).strip().endswith(
        '"expired": 1}'
    )
    expired = _fee_instruments(application_state(protocol))
    assert any(item["state"] == "expired" for item in expired)
    assert not [item for item in expired if item["state"] == "active"]

    start_payment(page, protocol, "pix")
    refreshed = _fee_instruments(application_state(protocol))
    assert len([item for item in refreshed if item["state"] == "active"]) == 1
    assert any(item["state"] == "expired" for item in refreshed)


# Cobre: TS-PAY-011
def test_E2E_PAY_011_candidato_nao_paga_taxa_de_outra_inscricao(
    page: Page,
    login,
    track_protocol,
    e2e_term,
    application_state,
    manage,
    created_user_emails,
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    fee_id = application_state(protocol)["fees"][0]["id"]

    suffix = uuid.uuid4().hex[:8]
    data = json.loads(
        manage("e2e_create_user", "--suffix", suffix).strip().splitlines()[-1]
    )
    created_user_emails.append(data["email"])
    page.context.clear_cookies()
    page.goto(f"{BASE_URL}/auth/login/")
    page.fill("#id_username", data["username"])
    page.fill("#id_password", data["password"])
    page.click("button[type='submit']")
    wait_for_page(page)

    response = page.goto(
        f"{BASE_URL}/pagamento/inscricao/{protocol}/?fee={fee_id}"
    )
    assert response is not None and response.status == 404
