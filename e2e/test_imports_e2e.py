"""E2E-CLI da importação legada (D-04 / TS-IMP)."""

from __future__ import annotations

from helpers import BASE_URL
from playwright.sync_api import Page, expect

FIXTURE = "/app/apps/imports/fixtures/legacy_e2e.json"
PROTOCOLS = ("990000001", "990000002", "990000003")


# Cobre: TS-IMP-001, TS-IMP-002, TS-IMP-003, TS-IMP-004, TS-IMP-005, TS-IMP-006, TS-IMP-007, TS-IMP-008
def test_E2E_IMP_001_importa_json_preserva_estado_e_detecta_duplicidade(
    manage,
    application_state,
    track_protocol,
    page: Page,
    login,
    login_as,
    create_term,
) -> None:
    manage("e2e_cleanup", "--purge-e2e-terms")
    output = manage("import_legacy_data", "--data", FIXTURE)
    assert "Criadas: 3" in output
    assert "storage não informada" in output
    for protocol in PROTOCOLS:
        track_protocol(protocol)

    project = application_state(PROTOCOLS[0])
    assert project["origin"] == "imported"
    assert project["owner"] is None
    assert project["lifecycle_status"] == "submitted"
    assert project["legacy_contact_email"] == "importada.a@example.com"
    assert project["legacy_contact_tax_id"] == "11111111111"
    assert any(
        fee["amount"] == "80.00" and fee["is_paid"] for fee in project["fees"]
    )
    assert project["dataset_audit_required"] is False

    consultation = application_state(PROTOCOLS[1])
    assert consultation["origin"] == "imported"
    assert consultation["modality"] == "consultation"
    assert consultation["owner"] is None

    # TS-IMP-002: sem resgate, não aparece no painel do candidato.
    login()
    page.goto(f"{BASE_URL}/painel/")
    expect(page.locator("body")).not_to_contain_text(PROTOCOLS[0])

    duplicate = manage("import_legacy_data", "--data", FIXTURE)
    assert "protocolo duplicado" in duplicate

    updated = manage(
        "import_legacy_data",
        "--data",
        FIXTURE,
        "--attachments-root",
        "/app/apps/imports/fixtures",
        "--update",
    )
    assert "protocolo duplicado" not in updated
    assert "storage não informada" not in updated
    assert "Arquivo ausente: 990000003/inexistente.pdf" in updated
    assert "Criadas: 3" in updated
    refreshed = application_state(PROTOCOLS[0])
    assert [(fee["type"], fee["amount"]) for fee in refreshed["fees"]] == [
        (fee["type"], fee["amount"]) for fee in project["fees"]
    ]
    assert [item["filename"] for item in refreshed["attachments"]] == [
        "arquivo-legado.pdf"
    ]
    assert refreshed["attachments"][0]["checksum"]

    # TS-IMP-006: transferência preserva ausência de dono e auditoria desligada.
    next_term = create_term()
    login_as("secretariat")
    page.goto(f"{BASE_URL}/inscricoes/{PROTOCOLS[0]}/")
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Transferir semestre')")
    expect(page.locator("h1.page-title")).to_be_visible()
    transferred = application_state(PROTOCOLS[0])
    assert transferred["term"]["id"] == next_term["id"]
    assert transferred["owner"] is None
    assert transferred["dataset_audit_required"] is False
