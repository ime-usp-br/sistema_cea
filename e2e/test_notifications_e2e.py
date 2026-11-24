"""E2E das notificações (TS-NOT-001..014)."""

from __future__ import annotations

from datetime import date, timedelta

from helpers import (
    BASE_URL,
    create_consultation_via_ui,
    create_project_via_ui,
    open_first_consultation_decision,
    open_first_screening_decision,
    open_teacher_feedback,
    pay_fee,
    register_decision,
    register_feedback,
    review_submission_by_protocol,
    schedule_consultation_for,
    schedule_screening_for,
    start_payment,
    submit_dataset_file,
    wait_for_page,
)
from playwright.sync_api import Page

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


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


# Cobre: TS-NOT-001
def test_E2E_NOT_001_submissao_notifica_candidato_e_cea(
    page: Page,
    login,
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
    state = application_state(protocol)
    candidate = _dispatch(state, "application_submitted_candidate")
    center = _dispatch(state, "application_submitted_center")
    assert candidate["status"] == "sent"
    assert center["status"] == "sent"
    assert candidate["recipient"] == candidate_account["email"]
    assert center["recipient"] == "cea-e2e@example.com"

    email = latest_email(
        to=candidate_account["email"],
        subject_contains=f"Inscrição {protocol} submetida com sucesso",
    )
    assert protocol in email["body"]
    center_email = latest_email(
        to="cea-e2e@example.com",
        subject_contains=f"Nova inscrição {protocol}",
    )
    assert protocol in center_email["body"]


# Cobre: TS-NOT-005
def test_E2E_NOT_005_cobranca_criada_notifica_candidato(
    page: Page,
    login,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
    latest_email,
) -> None:
    protocol = create_consultation_via_ui(
        page,
        login,
        track_protocol,
        e2e_term["id"],
        contact_email=candidate_account["email"],
    )
    start_payment(page, protocol, "pix")
    dispatch = _dispatch(application_state(protocol), "payment_created")
    assert dispatch["status"] == "sent"
    assert dispatch["recipient"] == candidate_account["email"]
    email = latest_email(
        to=candidate_account["email"],
        subject_contains=f"Pagamento disponível — inscrição {protocol}",
    )
    assert protocol in email["body"]


def _change_modality(page: Page, protocol: str) -> None:
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    row.locator("button:has-text('Mudar')").click()
    wait_for_page(page)


# Cobre: TS-NOT-011
def test_E2E_NOT_011_mudanca_de_modalidade_notifica_candidato(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
    latest_email,
) -> None:
    protocol = create_consultation_via_ui(
        page,
        login,
        track_protocol,
        e2e_term["id"],
        contact_email=candidate_account["email"],
    )
    login_as("secretariat")
    _change_modality(page, protocol)
    state = application_state(protocol)
    assert state["modality"] == "project"
    dispatch = _dispatch(state, "service_modality_changed")
    assert dispatch["status"] == "sent"
    assert dispatch["recipient"] == candidate_account["email"]
    email = latest_email(
        to=candidate_account["email"],
        subject_contains=f"Sua inscrição {protocol} foi alterada para Projeto",
    )
    assert "Projeto" in email["body"]


# Cobre: TS-NOT-014
def test_E2E_NOT_014_reemissao_de_boleto_tem_bcc_para_o_cea(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
) -> None:
    protocol = create_consultation_via_ui(
        page,
        login,
        track_protocol,
        e2e_term["id"],
        contact_email=candidate_account["email"],
    )
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    page.once("dialog", lambda dialog: dialog.accept())
    row.locator("button:has-text('Gerar Boleto (Manual)')").click()
    wait_for_page(page)

    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    page.click("button:has-text('Regenerar boleto')")
    wait_for_page(page)

    dispatch = _dispatch(application_state(protocol), "payment_slip_regenerated")
    assert dispatch["status"] == "sent"
    assert dispatch["recipient"] == candidate_account["email"]
    assert dispatch["bcc"] == ["cea-e2e@example.com"]


# Cobre: TS-NOT-012
def test_E2E_NOT_012_triagem_agendada_e_decidida_notifica_candidato(
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
    review_submission_by_protocol(page, protocol, "approved", "Dados adequados.")

    login_as("secretariat")
    schedule_screening_for(page, protocol, YESTERDAY)
    scheduled = _dispatch(application_state(protocol), "screening_scheduled")
    assert scheduled["status"] == "sent"
    assert scheduled["recipient"] == candidate_account["email"]
    latest_email(
        to=candidate_account["email"],
        subject_contains=f"Triagem agendada — inscrição {protocol}",
    )

    login_as("teacher")
    open_teacher_feedback(page, "/triagens/", protocol)
    register_feedback(page, "screening_completed")
    login_as("secretariat")
    open_first_screening_decision(page, protocol)
    register_decision(page, "approved_as_project")

    decided = _dispatch(application_state(protocol), "screening_decision")
    assert decided["status"] == "sent"
    assert decided["recipient"] == candidate_account["email"]
    latest_email(
        to=candidate_account["email"],
        subject_contains=f"Resultado da triagem — inscrição {protocol}",
    )


# Cobre: TS-NOT-013
def test_E2E_NOT_013_reuniao_agendada_e_decidida_notifica_candidato(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    candidate_account,
    latest_email,
) -> None:
    protocol = create_consultation_via_ui(
        page,
        login,
        track_protocol,
        e2e_term["id"],
        contact_email=candidate_account["email"],
    )
    pay_fee(page, protocol, "pix")

    login_as("secretariat")
    schedule_consultation_for(page, protocol, YESTERDAY)
    scheduled = _dispatch(application_state(protocol), "consultation_scheduled")
    assert scheduled["status"] == "sent"
    assert scheduled["recipient"] == candidate_account["email"]
    latest_email(
        to=candidate_account["email"],
        subject_contains=f"Reunião de consulta agendada — inscrição {protocol}",
    )

    login_as("teacher")
    open_teacher_feedback(page, "/reunioes/", protocol)
    register_feedback(page, "consultation_completed")
    login_as("secretariat")
    open_first_consultation_decision(page, protocol)
    register_decision(page, "approved_as_consultation")

    decided = _dispatch(application_state(protocol), "consultation_decision")
    assert decided["status"] == "sent"
    assert decided["recipient"] == candidate_account["email"]
    latest_email(
        to=candidate_account["email"],
        subject_contains=f"Resultado da reunião de consulta — inscrição {protocol}",
    )
