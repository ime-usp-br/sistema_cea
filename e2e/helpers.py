"""Helpers reutilizáveis dos testes E2E de navegador (Playwright)."""

from __future__ import annotations

from playwright.sync_api import Page

# A aplicação CEA é exposta em http://cea.local (reverse proxy nginx apontando
# para o container Django), conforme cadastrado no /etc/hosts.
BASE_URL = "http://cea.local"


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
