"""E2E do backoffice: cadastro de semestre, migração de transferência
pendente, lixeira/restauração, histórico, relatórios, exportações e PDFs."""

from __future__ import annotations

import json
from datetime import date

from helpers import (
    BASE_URL,
    create_consultation_via_ui,
    create_project_via_ui,
    fill_valid_project,
    pay_fee,
    set_application_term,
    submit_dataset_file,
    wait_for_page,
)
from playwright.sync_api import Page, expect


def _admin_create_term(page: Page, year: int) -> None:
    page.goto(f"{BASE_URL}/admin/terms/academicterm/add/")
    expect(page.locator("#id_year")).to_be_visible()
    page.fill("#id_year", str(year))
    page.select_option("#id_period", "first")
    if page.locator("#id_submission_start_date").count():
        page.fill("#id_submission_start_date", date.today().isoformat())
    if page.locator("#id_submission_end_date").count():
        page.fill("#id_submission_end_date", f"{year}-12-31")
    page.click("input[name='_save'], button[name='_save']")
    expect(page).to_have_url(__import__("re").compile(r".*/admin/terms/academicterm/$"))


def _application_in_term(
    page: Page, login, track_protocol, term: dict
) -> str:
    login()
    page.goto(f"{BASE_URL}/inscricoes/nova/")
    expect(page.locator("#form-inscricao")).to_be_visible()
    set_application_term(page, term["id"])
    fill_valid_project(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button[type='submit']")
    expect(page).to_have_url(__import__("re").compile(r".*/inscricoes/\d{9}/$"))
    protocol = page.url.rstrip("/").split("/")[-1]
    track_protocol(protocol)
    return protocol


# Cobre: TS-TRM-002, TS-TRM-003, TS-TRM-006
def test_E2E_TRM_001_002_003_cadastro_de_semestre_e_transferencia_pendente(
    page: Page,
    login,
    login_as,
    track_protocol,
    application_state,
    created_terms: list[int],
    manage,
    peek_term,
) -> None:
    base_year = peek_term()
    login_as("admin")
    _admin_create_term(page, base_year)
    base_term = json.loads(
        manage("e2e_create_term", "--year", str(base_year), "--period", "first")
        .strip()
        .splitlines()[-1]
    )
    created_terms.append(int(base_term["id"]))

    protocol = _application_in_term(page, login, track_protocol, base_term)

    # Sem próximo período: a transferência fica pendente (não retorna 500).
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Transferir semestre')")
    wait_for_page(page)
    state = application_state(protocol)
    assert state["transfer_pending"] is True
    expect(page.locator("body")).to_contain_text("transfer")

    # Criar o próximo semestre pelo admin conclui a migração automática.
    next_year = peek_term()
    login_as("admin")
    _admin_create_term(page, next_year)
    next_term = json.loads(
        manage("e2e_create_term", "--year", str(next_year), "--period", "first")
        .strip()
        .splitlines()[-1]
    )
    created_terms.append(int(next_term["id"]))

    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    state = application_state(protocol)
    assert state["term"]["year"] == next_year
    assert state["transfer_pending"] is False
    assert state["lifecycle_status"] == "awaiting_screening_scheduling"
    assert "term.transferred" in {e["code"] for e in state["events"]} or "term.transfer_auto" in {
        e["code"] for e in state["events"]
    }


# Cobre: TS-APP-010
def test_E2E_APP_010_exclusao_logica_e_restauracao(
    page: Page, login, login_as, track_protocol, e2e_term, application_state
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    row.locator("button:has-text('Excluir')").click()
    wait_for_page(page)

    page.goto(f"{BASE_URL}/inscricoes/excluidas/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    row.locator("button:has-text('Restaurar')").click()
    wait_for_page(page)
    page.goto(f"{BASE_URL}/inscricoes/?term=all")
    expect(page.locator("body")).to_contain_text(protocol)
    state = application_state(protocol)
    assert state["soft_deleted"] is False


# Cobre: TS-EVT-001
def test_E2E_EVT_001_historico_lista_eventos_da_inscricao(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/historico/?term=all")
    wait_for_page(page)
    expect(page.locator("body")).to_contain_text(protocol)
    expect(page.locator("body")).to_contain_text("Inscrição criada")


# Cobre: TS-FEE-002, TS-REP-001, TS-REP-004, TS-REP-005
def test_E2E_REP_001_004_005_relatorio_financeiro_e_exportacoes(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    login_as("secretariat")
    page.goto(f"{BASE_URL}/gestao/relatorios/financeiro/?term=all")
    wait_for_page(page, "Relatório Financeiro")
    expect(page.locator("body")).to_contain_text(protocol)
    expect(page.locator("body")).to_contain_text("R$ 140,00")

    csv = page.request.get(f"{BASE_URL}/gestao/relatorios/financeiro/csv/?term=all")
    assert csv.status == 200
    assert protocol.encode() in csv.body()

    xlsx = page.request.get(f"{BASE_URL}/gestao/relatorios/financeiro/xlsx/?term=all")
    assert xlsx.status == 200
    # Com openpyxl instalado o conteúdo é XLSX (zip "PK"); sem ele o serviço
    # cai no fallback TSV (TS-REP-005). Em ambos os casos o protocolo aparece.
    body = xlsx.body()
    assert body.startswith(b"PK") or protocol.encode() in body
    assert "attachment" in xlsx.headers.get("content-disposition", "")


# Cobre: TS-REP-006
def test_E2E_REP_006_relatorio_de_auditoria(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = create_project_via_ui(page, login, track_protocol, e2e_term["id"])
    pay_fee(page, protocol, "pix")
    submit_dataset_file(page, protocol)
    login_as("secretariat")
    page.goto(f"{BASE_URL}/gestao/relatorios/auditoria/?term=all")
    wait_for_page(page)
    expect(page.locator("body")).to_contain_text(protocol)


# Cobre: TS-PAY-022
def test_E2E_PAY_022_pagamentos_pendentes_lista_inscricao(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    protocol = create_consultation_via_ui(page, login, track_protocol, e2e_term["id"])
    login_as("secretariat")
    page.goto(f"{BASE_URL}/pagamentos/pendentes/")
    wait_for_page(page)
    expect(page.locator("body")).to_contain_text(protocol)


# Cobre: TS-APP-008, TS-AUD-018, TS-FILE-002
def test_E2E_DOC_001_pdfs_e_anexos_baixam(
    page: Page, login, login_as, track_protocol, e2e_term
) -> None:
    login()
    page.goto(f"{BASE_URL}/inscricoes/nova/")
    expect(page.locator("#form-inscricao")).to_be_visible()
    set_application_term(page, e2e_term["id"])
    fill_valid_project(page)
    page.set_input_files('input[name="attachments"]', {
        "name": "documento-e2e.pdf",
        "mimeType": "application/pdf",
        "buffer": b"%PDF-1.4\n% anexo E2E\n%%EOF\n",
    })
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button[type='submit']")
    expect(page).to_have_url(__import__("re").compile(r".*/inscricoes/\d{9}/$"))
    protocol = page.url.rstrip("/").split("/")[-1]
    track_protocol(protocol)

    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    full = page.request.get(f"{BASE_URL}/inscricoes/{protocol}/pdf/ficha/")
    first = page.request.get(f"{BASE_URL}/inscricoes/{protocol}/pdf/primeira-pagina/")
    assert full.status == 200 and full.body().startswith(b"%PDF")
    assert first.status == 200 and first.body().startswith(b"%PDF")

    attachment_link = page.locator("a", has_text="documento-e2e.pdf").first.get_attribute("href")
    attachment = page.request.get(f"{BASE_URL}{attachment_link}")
    assert attachment.status == 200
