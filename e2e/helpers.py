"""Helpers reutilizáveis dos testes E2E de navegador (Playwright)."""

from __future__ import annotations

import os

from playwright.sync_api import Page, expect

# URL da aplicação sob teste. Configurável por E2E_BASE_URL; o padrão aponta
# para o ambiente de desenvolvimento publicado em cea.dev.ime.
BASE_URL = os.getenv("E2E_BASE_URL", "http://cea.dev.ime").rstrip("/")


def wait_for_page(page: Page, title: str | None = None) -> None:
    """Espera o carregamento por um locator estável, sem ``networkidle``."""
    heading = page.locator("h1.page-title")
    expect(heading).to_be_visible()
    if title:
        expect(heading).to_contain_text(title)


def select_catalog_option(page: Page, code: str, category: str | None = None) -> None:
    """Marca uma opção de catálogo pelo atributo ``data-code``.

    ``category`` (opcional) desambigua opções com o mesmo ``data-code`` em
    categorias distintas (ex.: ``other`` existe em todas as seções).
    """
    selector = f'input[name="catalog_options"][data-code="{code}"]'
    if category:
        selector += f'[data-category="{category}"]'
    page.locator(selector).check(force=True)


def fill_project_descriptive_fields(page: Page) -> None:
    """Preenche os campos descritivos do projeto (itens 1 a 9)."""
    project_fields = {
        "project_title": "Estudo de viabilidade estatística",
        "context_summary": "Aspectos gerais da área de concentração que motivaram o projeto.",
        "general_objectives": "Avaliar a associação entre as variáveis de interesse.",
        "variables_and_measurements": "Variáveis categóricas e contínuas medidas de forma padronizada.",
        "contextual_factors": "Fatores ambientais controlados durante a coleta.",
        "sampling_and_limitations": "Amostra de 120 unidades, com restrições de tempo e custo.",
        "data_management_plan": "Dados armazenados em planilhas e servidor seguro.",
        "expected_results": "Conclusões descritivas e modelagem preliminar.",
        "expected_support": "Suporte estatístico para análise e interpretação dos resultados.",
    }
    for name, value in project_fields.items():
        page.fill(f'textarea[name="{name}"], input[name="{name}"]', value)


def fill_required_basic_fields(page: Page) -> None:
    """Preenche os campos pessoais obrigatórios (comum a Projeto e Consulta)."""
    page.fill('input[name="researcher_name"]', "Pesquisadora Teste E2E")
    page.fill('input[name="contact_email"]', "e2e.pesquisadora@example.com")
    page.fill('input[name="contact_email_confirmation"]', "e2e.pesquisadora@example.com")
    page.fill('input[name="contact_phone"]', "(11) 99999-0000")
    page.fill('input[name="tax_id"]', "529.982.247-25")
    page.fill('input[name="institution_name"]', "USP")
    page.fill('input[name="course_name"]', "Estatística")
    page.check('input[name="data_use_authorization_accepted"]')


def fill_valid_project(page: Page) -> None:
    """Preenche uma inscrição de Projeto 100% válida (inclui orientador)."""
    page.check('input[name="modality"][value="project"]')
    page.check('input[name="data_already_collected"][value="true"]')
    fill_required_basic_fields(page)
    page.fill('input[name="mentor_name"]', "Profa. Orientadora Teste")
    page.check('input[name="mentor_declaration_accepted"]')
    select_catalog_option(page, "student")
    select_catalog_option(page, "undergraduate_research")
    select_catalog_option(page, "health_biological")
    select_catalog_option(page, "fapesp")
    fill_project_descriptive_fields(page)


def fill_valid_consultation(page: Page) -> None:
    """Preenche uma inscrição de Consulta válida (sem campos de projeto)."""
    page.check('input[name="modality"][value="consultation"]')
    fill_required_basic_fields(page)
    select_catalog_option(page, "student")
    select_catalog_option(page, "publication")
    select_catalog_option(page, "social_human")
    select_catalog_option(page, "cnpq")


# ---------------------------------------------------------------------------
# Helpers de jornada (pagamento, auditoria, agendamento e decisão)
# ---------------------------------------------------------------------------


def pay_fee(page: Page, protocol: str, method: str = "pix") -> None:
    """Paga a próxima taxa pendente pela UI e confirma via rota de simulação."""
    page.goto(f"{BASE_URL}/pagamento/inscricao/{protocol}/")
    wait_for_page(page, "Pagamento")
    page.select_option('select[name="method"]', method)
    page.click("button[type='submit']")
    expect(page.locator("button:has-text('Simular pagamento (dev)')")).to_be_visible()
    simulate_payment(page)


def simulate_payment(page: Page) -> None:
    """Aciona o botão só-DEBUG de confirmação de pagamento da tela atual."""
    page.click("button:has-text('Simular pagamento (dev)')")
    wait_for_page(page)


def submit_dataset_external_link(
    page: Page, protocol: str, url: str = "https://example.com/dados-e2e"
) -> None:
    """Candidato envia dados para auditoria por link externo."""
    page.goto(f"{BASE_URL}/auditoria/inscricao/{protocol}/enviar/")
    expect(page.locator('select[name="channel"]')).to_be_visible()
    page.select_option('select[name="channel"]', "external_link")
    page.fill('input[name="external_url"]', url)
    page.check('input[name="external_link_declaration"]')
    page.click("button[type='submit']")
    wait_for_page(page)


def review_submission(page: Page, outcome: str, note: str = "Revisão E2E") -> None:
    """Docente revisa a submissão aberta na fila (`outcome` no vocabulário do form)."""
    expect(page.locator('select[name="outcome"]')).to_be_visible()
    page.select_option('select[name="outcome"]', outcome)
    page.fill('textarea[name="note"]', note)
    page.click("button[type='submit']")
    wait_for_page(page)


def schedule_screening(page: Page, protocol: str, date_str: str) -> None:
    """Secretaria agenda uma triagem online para uma data (YYYY-MM-DD)."""
    page.goto(f"{BASE_URL}/agendamentos/triagem/{protocol}/")
    expect(page.locator('input[name="scheduled_date"]')).to_be_visible()
    page.fill('input[name="scheduled_date"]', date_str)
    page.fill('input[name="scheduled_time"]', "10:00")
    page.select_option('select[name="meeting_mode"]', "online")
    page.fill('input[name="virtual_link"]', "https://meet.example.com/e2e")
    page.click("button[type='submit']")
    wait_for_page(page)


def schedule_consultation(page: Page, protocol: str, date_str: str) -> None:
    """Secretaria agenda uma reunião de consulta online para uma data (YYYY-MM-DD)."""
    page.goto(f"{BASE_URL}/agendamentos/reuniao/{protocol}/")
    expect(page.locator('input[name="scheduled_date"]')).to_be_visible()
    page.fill('input[name="scheduled_date"]', date_str)
    page.fill('input[name="scheduled_time"]', "10:00")
    page.select_option('select[name="meeting_mode"]', "online")
    page.fill('input[name="virtual_link"]', "https://meet.example.com/e2e")
    page.click("button[type='submit']")
    wait_for_page(page)


def register_feedback(page: Page, feedback: str) -> None:
    """Docente registra o feedback na tela de decisão aberta."""
    expect(page.locator('select[name="teacher_feedback"]')).to_be_visible()
    page.select_option('select[name="teacher_feedback"]', feedback)
    page.click("button[name='submit_feedback']")
    wait_for_page(page)


def register_decision(page: Page, decision: str) -> None:
    """Secretaria registra a decisão na tela de decisão aberta."""
    expect(page.locator('select[name="decision"]')).to_be_visible()
    page.select_option('select[name="decision"]', decision)
    page.click("button:has-text('Registrar decisão')")
    wait_for_page(page)
