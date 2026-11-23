"""E2E das notificações P0 (TS-NOT-002/003/004/006/007/008)."""

from __future__ import annotations

from helpers import (
    BASE_URL,
    create_consultation_via_ui,
    create_project_via_ui,
    pay_fee,
    review_submission_by_protocol,
    start_payment,
    submit_dataset_file,
    wait_for_page,
)
from playwright.sync_api import Page


def _dispatch(state: dict, template: str) -> dict:
    return next(
        item for item in state["notifications"] if item["template"] == template
    )


# Cobre: TS-NOT-002, TS-NOT-003
def test_E2E_NOT_002_003_correcao_e_aprovacao_notificam_candidato(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
    latest_email,
) -> None:
    protocol = create_project_via_ui(
        page,
        login,
        track_protocol,
        e2e_term["id"],
        contact_email=candidate_account["email"],
    )
    pay_fee(page, protocol, "pix")
    submit_dataset_file(page, protocol)

    login_as("teacher")
    review_submission_by_protocol(
        page, protocol, "needs_correction", "Ajuste os dados do projeto."
    )
    state = application_state(protocol)
    correction = _dispatch(state, "dataset_correction_requested")
    assert correction["status"] == "sent"
    assert correction["recipient"] == candidate_account["email"]
    email = latest_email(
        to=candidate_account["email"], subject_contains="Correção solicitada"
    )
    assert "Ajuste os dados do projeto." in email["body"]

    login()
    submit_dataset_file(page, protocol)
    login_as("teacher")
    review_submission_by_protocol(page, protocol, "approved", "Dados adequados.")
    state = application_state(protocol)
    approved = _dispatch(state, "dataset_approved")
    assert approved["status"] == "sent"
    assert approved["recipient"] == candidate_account["email"]
    email = latest_email(
        to=candidate_account["email"], subject_contains="Dados aprovados"
    )
    assert "pagamento" in email["body"].lower()


# Cobre: TS-NOT-004
def test_E2E_NOT_004_rejeicao_notifica_candidato_e_secretaria(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
    latest_email,
) -> None:
    protocol = create_project_via_ui(
        page,
        login,
        track_protocol,
        e2e_term["id"],
        contact_email=candidate_account["email"],
    )
    pay_fee(page, protocol, "pix")
    submit_dataset_file(page, protocol)

    login_as("teacher")
    review_submission_by_protocol(
        page, protocol, "rejected", "Dados inconsistentes com o projeto."
    )
    state = application_state(protocol)
    candidate_dispatch = _dispatch(state, "dataset_rejected")
    secretariat_dispatch = _dispatch(state, "dataset_rejected_secretariat")
    assert candidate_dispatch["status"] == "sent"
    assert secretariat_dispatch["status"] == "sent"
    assert candidate_dispatch["recipient"] == candidate_account["email"]

    candidate_email = latest_email(
        to=candidate_account["email"], subject_contains="Dados rejeitados"
    )
    assert "Dados inconsistentes" in candidate_email["body"]
    secretariat_email = latest_email(
        to=secretariat_dispatch["recipient"],
        subject_contains=f"Rejeição de dados — inscrição {protocol}",
    )
    assert protocol in secretariat_email["body"]


# Cobre: TS-NOT-006, TS-NOT-007
def test_E2E_NOT_006_007_pagamento_confirmado_notifica_candidato(
    page: Page,
    login,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
    latest_email,
) -> None:
    for method in ("pix", "boleto"):
        protocol = create_consultation_via_ui(
            page,
            login,
            track_protocol,
            e2e_term["id"],
            contact_email=candidate_account["email"],
        )
        pay_fee(page, protocol, method)
        state = application_state(protocol)
        dispatch = _dispatch(state, "payment_confirmed")
        assert dispatch["status"] == "sent"
        assert dispatch["recipient"] == candidate_account["email"]
        email = latest_email(
            to=candidate_account["email"],
            subject_contains=f"Pagamento confirmado — inscrição {protocol}",
        )
        assert protocol in email["body"]


# Cobre: TS-NOT-008
def test_E2E_NOT_008_pagamento_manual_nao_notifica_candidato(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
    mailbox,
    manage,
) -> None:
    protocol = create_consultation_via_ui(
        page,
        login,
        track_protocol,
        e2e_term["id"],
        contact_email=candidate_account["email"],
    )
    start_payment(page, protocol, "boleto")
    manage("e2e_backdate_bank_slip", "--protocol", protocol)

    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("a:has-text('Confirmar Pagamento (Depósito)')")
    wait_for_page(page, "Confirmar pagamento manual")
    page.fill('textarea[name="note"]', "Depósito identificado.")
    page.click("button:has-text('Confirmar pagamento')")
    wait_for_page(page, "Confirmar pagamento manual")

    state = application_state(protocol)
    assert state["payment_state"] == "paid"
    assert all(
        item["template"] != "payment_confirmed" for item in state["notifications"]
    )
    assert mailbox(
        to=candidate_account["email"], subject_contains="Pagamento confirmado"
    ) == []
