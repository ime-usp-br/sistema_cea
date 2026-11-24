"""E2E da auditoria de dados: envio por arquivo/link, correção, aprovação,
rejeição e resolução administrativa."""

from __future__ import annotations

import uuid

import pytest
from helpers import (
    BASE_URL,
    create_consultation_via_ui,
    create_project_via_ui,
    pay_fee,
    review_submission,
    review_submission_by_protocol,
    submit_dataset_external_link,
    submit_dataset_file,
    wait_for_page,
)
from playwright.sync_api import Page, expect


def _awaiting_review(
    page: Page,
    login,
    track_protocol,
    e2e_term: dict,
    modality: str = "project",
    channel: str = "external_link",
) -> str:
    creator = (
        create_project_via_ui
        if modality == "project"
        else create_consultation_via_ui
    )
    protocol = creator(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    if channel == "file":
        submit_dataset_file(page, protocol)
    else:
        submit_dataset_external_link(page, protocol)
    return protocol


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
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_review(
        page, login, track_protocol, e2e_term, channel="file"
    )

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
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
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
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_review(page, login, track_protocol, e2e_term)

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
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = _awaiting_review(page, login, track_protocol, e2e_term)

    login_as("teacher")
    review_submission_by_protocol(page, protocol, "rejected", "Dados inconsistentes.")
    _resolve_rejected(page, login_as, protocol, "reject_application")
    state = application_state(protocol)
    assert state["lifecycle_status"] == "not_approved"


# Cobre: TS-AUD-015, TS-TRM-004
def test_E2E_AUD_015_transferencia_de_periodo(
    page: Page,
    login,
    login_as,
    track_protocol,
    e2e_term,
    application_state,
    create_term,
) -> None:
    protocol = _awaiting_review(page, login, track_protocol, e2e_term)
    target = create_term(2042, "first")

    login_as("teacher")
    review_submission_by_protocol(page, protocol, "rejected", "Transferir.")
    _resolve_rejected(
        page, login_as, protocol, "transfer_term", target_term=str(target["id"])
    )
    state = application_state(protocol)
    assert state["term"]["id"] == target["id"]
    assert state["audit_submissions"][0]["resolutions"][0]["resolution"] == "transfer_term"


# Cobre: TS-AUD-002
def test_E2E_AUD_002_projeto_importado_sem_dono_nao_entra_em_auditoria(
    page: Page,
    login,
    track_protocol,
    manage,
    candidate_account,
) -> None:
    protocol = f"{uuid.uuid4().int % 1_000_000_000:09d}"
    manage(
        "e2e_create_imported_application",
        "--protocol",
        protocol,
        "--contact-email",
        candidate_account["email"],
    )
    track_protocol(protocol)
    login()
    response = page.goto(f"{BASE_URL}/auditoria/inscricao/{protocol}/enviar/")
    assert response is not None and response.status == 404


# Cobre: TS-AUD-004
def test_E2E_AUD_004_arquivo_acima_de_10mb_e_rejeitado(
    page: Page, login, track_protocol, e2e_term
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    page.goto(f"{BASE_URL}/auditoria/inscricao/{protocol}/enviar/")
    page.select_option('select[name="channel"]', "file")
    page.set_input_files(
        'input[name="file"]',
        files=[
            {
                "name": "grande.pdf",
                "mimeType": "application/pdf",
                "buffer": b"x" * (10 * 1024 * 1024 + 1),
            }
        ],
    )
    with page.expect_response(
        lambda response: response.request.method == "POST"
    ) as response_info:
        page.click("button[type='submit']")
    assert response_info.value.status == 400
    expect(page.locator("body")).to_contain_text("10 MB")


# Cobre: TS-AUD-008
def test_E2E_AUD_008_arquivo_e_link_simultaneos_sao_rejeitados(
    page: Page, login, track_protocol, e2e_term
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")

    page.goto(f"{BASE_URL}/auditoria/inscricao/{protocol}/enviar/")
    page.select_option('select[name="channel"]', "file")
    page.set_input_files(
        'input[name="file"]',
        files=[{"name": "dados.csv", "mimeType": "text/csv", "buffer": b"a,b\n1,2\n"}],
    )
    page.fill('input[name="external_url"]', "https://example.com/dados")
    with page.expect_response(
        lambda response: response.request.method == "POST"
    ) as response_info:
        page.click("button[type='submit']")
    assert response_info.value.status == 400
    expect(page.locator("body")).to_contain_text("Não informe um link")

    page.goto(f"{BASE_URL}/auditoria/inscricao/{protocol}/enviar/")
    page.select_option('select[name="channel"]', "external_link")
    page.fill('input[name="external_url"]', "https://example.com/dados")
    page.check('input[name="external_link_declaration"]')
    page.set_input_files(
        'input[name="file"]',
        files=[{"name": "dados.csv", "mimeType": "text/csv", "buffer": b"a,b\n1,2\n"}],
    )
    with page.expect_response(
        lambda response: response.request.method == "POST"
    ) as response_info:
        page.click("button[type='submit']")
    assert response_info.value.status == 400
    expect(page.locator("body")).to_contain_text("Não envie um arquivo")
