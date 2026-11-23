"""E2E de triagens e reuniões de consulta: agendamento, reagendamento,
cancelamento, feedback obrigatório e decisões alternativas."""

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
    submit_dataset_file,
    wait_for_page,
)
from playwright.sync_api import Page, expect

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def _awaiting_screening(
    page: Page, login, login_as, track_protocol, e2e_term: dict
) -> str:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    submit_dataset_file(page, protocol)
    login_as("teacher")
    review_submission_by_protocol(page, protocol, "approved", "Dados adequados.")
    return protocol


def _awaiting_consultation(
    page: Page, login, track_protocol, e2e_term: dict
) -> str:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    return protocol


# Cobre: TS-MEET-007, TS-MEET-008
def test_E2E_MEET_007_008_reagendar_e_cancelar_triagem(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_screening(
        page, login, login_as, track_protocol, e2e_term
    )
    login_as("secretariat")
    schedule_screening_for(page, protocol, YESTERDAY)

    # Reagenda mantendo o modo online.
    page.goto(f"{BASE_URL}/agendamentos/triagem/{protocol}/")
    wait_for_page(page)
    page.fill('input[name="scheduled_date"]', date.today().isoformat())
    page.fill('input[name="scheduled_time"]', "14:30")
    page.select_option('select[name="meeting_mode"]', "online")
    page.fill('input[name="virtual_link"]', "https://meet.example.com/reagendada")
    page.click("button[type='submit']")
    wait_for_page(page)
    state = application_state(protocol)
    assert state["screening"]["state"] == "rescheduled"
    assert state["lifecycle_status"] == "awaiting_screening_result"

    # Cancela e a inscrição volta a aguardar agendamento.
    page.goto(f"{BASE_URL}/agendamentos/triagem/{protocol}/")
    wait_for_page(page)
    page.click("button:has-text('Cancelar triagem')")
    wait_for_page(page)
    state = application_state(protocol)
    assert state["screening"]["state"] == "canceled"
    assert state["lifecycle_status"] == "awaiting_screening_scheduling"


# Cobre: TS-MEET-012
def test_E2E_MEET_012_feedback_bloqueado_antes_do_evento(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = _awaiting_screening(
        page, login, login_as, track_protocol, e2e_term
    )
    login_as("secretariat")
    schedule_screening_for(page, protocol, (date.today() + timedelta(days=2)).isoformat())

    login_as("teacher")
    open_teacher_feedback(page, "/triagens/", protocol)
    page.select_option('select[name="teacher_feedback"]', "screening_completed")
    page.click("button[name='submit_feedback']")
    expect(page.locator("body")).to_contain_text(
        "só pode ser registrado após a data e hora do evento"
    )


# Cobre: TS-FEE-005, TS-MEET-010
def test_E2E_MEET_010_triagem_aprovada_como_consulta_gera_complemento(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_screening(
        page, login, login_as, track_protocol, e2e_term
    )
    login_as("secretariat")
    schedule_screening_for(page, protocol, YESTERDAY)

    login_as("teacher")
    open_teacher_feedback(page, "/triagens/", protocol)
    register_feedback(page, "screening_completed")

    login_as("secretariat")
    open_first_screening_decision(page, protocol)
    register_decision(page, "approved_as_consultation")

    state = application_state(protocol)
    assert state["modality"] == "consultation"
    assert state["lifecycle_status"] == "approved_as_consultation"
    supplement = next(fee for fee in state["fees"] if fee["type"] == "supplement_fee")
    assert supplement["amount"] == "60.00"

    # O complemento ainda pode ser pago pela área do candidato.
    login()
    pay_fee(page, protocol, method="pix")
    state = application_state(protocol)
    assert state["payment_state"] == "paid"
    assert state["lifecycle_status"] == "approved_as_consultation"


# Cobre: TS-MEET-011
def test_E2E_MEET_011_triagem_nao_aprovada(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_screening(
        page, login, login_as, track_protocol, e2e_term
    )
    login_as("secretariat")
    schedule_screening_for(page, protocol, YESTERDAY)
    login_as("teacher")
    open_teacher_feedback(page, "/triagens/", protocol)
    register_feedback(page, "screening_not_completed")
    login_as("secretariat")
    open_first_screening_decision(page, protocol)
    register_decision(page, "not_approved")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "not_approved"
    assert state["screening"]["decision"] == "not_approved"


# Cobre: TS-MEET-003, TS-MEET-007, TS-MEET-008
def test_E2E_MEET_003_007_008_reuniao_reagendar_cancelar(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_consultation(
        page, login, track_protocol, e2e_term
    )
    login_as("secretariat")
    schedule_consultation_for(page, protocol, YESTERDAY)

    page.goto(f"{BASE_URL}/agendamentos/reuniao/{protocol}/")
    wait_for_page(page)
    page.fill('input[name="scheduled_date"]', date.today().isoformat())
    page.fill('input[name="scheduled_time"]', "15:00")
    page.select_option('select[name="meeting_mode"]', "in_person")
    page.fill('input[name="place"]', "Sala 2")
    page.click("button[type='submit']")
    wait_for_page(page)
    state = application_state(protocol)
    assert state["consultation"]["state"] == "rescheduled"
    assert state["lifecycle_status"] == "awaiting_consultation_result"

    page.goto(f"{BASE_URL}/agendamentos/reuniao/{protocol}/")
    wait_for_page(page)
    page.click("button:has-text('Cancelar reunião')")
    wait_for_page(page)
    state = application_state(protocol)
    assert state["consultation"]["state"] == "canceled"
    assert state["lifecycle_status"] == "awaiting_consultation_scheduling"


# Cobre: TS-FEE-004, TS-MEET-014
def test_E2E_MEET_014_consulta_aprovada_como_projeto_gera_taxa_com_credito(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_consultation(
        page, login, track_protocol, e2e_term
    )
    login_as("secretariat")
    schedule_consultation_for(page, protocol, YESTERDAY)

    login_as("teacher")
    open_teacher_feedback(page, "/reunioes/", protocol)
    register_feedback(page, "consultation_completed")

    login_as("secretariat")
    open_first_consultation_decision(page, protocol)
    register_decision(page, "approved_as_project")

    state = application_state(protocol)
    assert state["modality"] == "project"
    assert state["lifecycle_status"] == "awaiting_payment"
    project_fee = next(fee for fee in state["fees"] if fee["type"] == "project_fee")
    assert project_fee["amount"] == "190.00"

    login()
    pay_fee(page, protocol, method="pix")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "approved_as_project"
    assert state["payment_state"] == "paid"
