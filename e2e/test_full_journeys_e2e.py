"""Jornadas completas de navegador: cadastro, inscrição, pagamento, auditoria,
agendamento, feedback, decisão e estado final.

Os dados de apoio (usuários) vêm do ``seed_e2e``. A inscrição nasce na própria
UI; cada etapa é executada pelo perfil real (candidato, docente, secretaria).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from helpers import (
    assert_status_page,
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
    submit_dataset_external_link,
)
from playwright.sync_api import Page, expect


# Cobre: TS-APP-002, TS-AUD-001, TS-AUD-011, TS-EVT-002, TS-FEE-001, TS-MEET-001, TS-MEET-009, TS-MEET-012, TS-PAY-008
@pytest.mark.p0
def test_E2E_PROJECT_001_jornada_completa_ate_aprovado_como_projeto(
    page: Page,
    login,
    login_as,
    track_protocol,
    application_state,
    e2e_term,
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    assert_status_page(page, protocol, "Aguardando pagamento")

    # 1. Taxa de inscrição via Pix (gateway simulado) + confirmação local.
    pay_fee(page, protocol, method="pix")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_dataset_submission"
    assert state["payment_state"] == "paid"

    # 2. Envio de dados por link externo.
    submit_dataset_external_link(page, protocol, "https://example.com/dados-e2e")
    expect(page.locator("body")).to_contain_text("Aguardando análise de dados")

    # 3. Docente aprova a auditoria.
    login_as("teacher")
    review_submission_by_protocol(page, protocol, "approved", "Dados adequados.")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_screening_scheduling"

    # 4. Secretaria agenda a triagem para ontem (feedback exige evento passado).
    login_as("secretariat")
    schedule_screening_for(
        page, protocol, (date.today() - timedelta(days=1)).isoformat()
    )
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_screening_result"

    # 5. Docente registra o feedback.
    login_as("teacher")
    open_teacher_feedback(page, "/triagens/", protocol)
    register_feedback(page, "screening_completed")

    # 6. Secretaria decide aprovado como projeto, gerando a Taxa de Projeto.
    login_as("secretariat")
    open_first_screening_decision(page, protocol)
    register_decision(page, "approved_as_project")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_payment"
    assert any(fee["type"] == "project_fee" for fee in state["fees"])

    # 7. Candidato paga a Taxa de Projeto pela UI e a inscrição é concluída.
    login()
    pay_fee(page, protocol, method="pix")
    assert_status_page(page, protocol, "Aprovado como Projeto")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "approved_as_project"
    assert state["payment_state"] == "paid"
    assert state["screening"]["decision"] == "approved_as_project"
    assert state["screening"]["teacher_feedback"] == "screening_completed"
    assert {event["code"] for event in state["events"]} >= {
        "application.created",
        "pix.confirmed",
        "audit.submitted",
        "audit.reviewed",
        "meeting.screening_scheduled",
        "meeting.screening_feedback_recorded",
        "meeting.screening_decided",
    }


# Cobre: TS-APP-003, TS-BSL-005, TS-FEE-002, TS-MEET-003, TS-MEET-012, TS-PAY-002
@pytest.mark.p0
def test_E2E_CONSULTATION_001_jornada_completa_com_boleto(
    page: Page,
    login,
    login_as,
    track_protocol,
    application_state,
    e2e_term,
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    assert_status_page(page, protocol, "Aguardando pagamento")

    # 1. Taxa de inscrição via boleto (SOAP simulado) + confirmação local.
    pay_fee(page, protocol, method="boleto")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_consultation_scheduling"
    assert state["payment_state"] == "paid"
    assert any(
        instrument["method"] == "bank_slip" and instrument["state"] == "paid"
        for fee in state["fees"]
        for instrument in fee["instruments"]
    )

    # 2. Secretaria agenda a reunião de consulta.
    login_as("secretariat")
    schedule_consultation_for(
        page, protocol, (date.today() - timedelta(days=1)).isoformat()
    )
    state = application_state(protocol)
    assert state["lifecycle_status"] == "awaiting_consultation_result"

    # 3. Docente registra o feedback.
    login_as("teacher")
    open_teacher_feedback(page, "/reunioes/", protocol)
    register_feedback(page, "consultation_completed")

    # 4. Secretaria decide aprovado como consulta (terminal).
    login_as("secretariat")
    open_first_consultation_decision(page, protocol)
    register_decision(page, "approved_as_consultation")

    login()
    assert_status_page(page, protocol, "Aprovado como Consulta")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "approved_as_consultation"
    assert state["consultation"]["decision"] == "approved_as_consultation"
    assert state["consultation"]["teacher_feedback"] == "consultation_completed"
    assert "bank_slip.paid" in {event["code"] for event in state["events"]}
