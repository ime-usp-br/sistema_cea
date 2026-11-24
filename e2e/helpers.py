"""Helpers reutilizáveis dos testes E2E de navegador (Playwright)."""

from __future__ import annotations

import json as _json
import os
import re as _re
import urllib.error as _urlerror
import urllib.request as _urlrequest

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
    page.fill('input[name="researcher_name"]', "Pesquisadora Teste Exemplo")
    page.fill('input[name="contact_email"]', "e2e.pesquisadora@example.com")
    page.fill('input[name="contact_email_confirmation"]', "e2e.pesquisadora@example.com")
    page.fill('input[name="contact_phone"]', "(11) 99999-0000")
    page.fill('input[name="tax_id"]', "529.982.247-25")
    page.fill('input[name="institution_name"]', "USP")
    page.fill('input[name="course_name"]', "Estatística")
    page.check('input[name="data_use_authorization_accepted"]')


def fill_valid_project(page: Page, ensure_modality: bool = True) -> None:
    """Preenche uma inscrição de Projeto 100% válida (inclui orientador)."""
    if ensure_modality and not page.is_checked(
        'input[name="modality"][value="project"]'
    ):
        page.check('input[name="modality"][value="project"]')
    if not page.is_checked('input[name="data_already_collected"][value="true"]'):
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
    if not page.is_checked('input[name="modality"][value="consultation"]'):
        page.check('input[name="modality"][value="consultation"]')
    fill_required_basic_fields(page)
    select_catalog_option(page, "student")
    select_catalog_option(page, "publication")
    select_catalog_option(page, "social_human")
    select_catalog_option(page, "cnpq")


def create_project_via_ui(
    page: Page,
    login,
    track_protocol,
    term_id: int | str,
    contact_email: str | None = None,
) -> str:
    """Cria uma inscrição de Projeto pela UI e devolve o protocolo."""
    login()
    page.goto(f"{BASE_URL}/inscricoes/nova/")
    expect(page.locator("#form-inscricao")).to_be_visible()
    set_application_term(page, term_id)
    fill_valid_project(page)
    if contact_email:
        page.fill('input[name="contact_email"]', contact_email)
        page.fill('input[name="contact_email_confirmation"]', contact_email)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button[type='submit']")
    expect(page).to_have_url(_re.compile(r".*/inscricoes/\d{9}/$"))
    protocol = page.url.rstrip("/").split("/")[-1]
    track_protocol(protocol)
    return protocol


def create_consultation_via_ui(
    page: Page,
    login,
    track_protocol,
    term_id: int | str,
    contact_email: str | None = None,
) -> str:
    """Cria uma inscrição de Consulta pela UI e devolve o protocolo."""
    login()
    page.goto(f"{BASE_URL}/inscricoes/nova/")
    expect(page.locator("#form-inscricao")).to_be_visible()
    set_application_term(page, term_id)
    fill_valid_consultation(page)
    if contact_email:
        page.fill('input[name="contact_email"]', contact_email)
        page.fill('input[name="contact_email_confirmation"]', contact_email)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("button[type='submit']")
    expect(page).to_have_url(_re.compile(r".*/inscricoes/\d{9}/$"))
    protocol = page.url.rstrip("/").split("/")[-1]
    track_protocol(protocol)
    return protocol


# ---------------------------------------------------------------------------
# Helpers de jornada (pagamento, auditoria, agendamento e decisão)
# ---------------------------------------------------------------------------


def _payment_method_value(method: str) -> str:
    """Traduz o vocabulário do comando para o valor do formulário."""
    return "bank_slip" if method == "boleto" else method


def pay_fee(page: Page, protocol: str, method: str = "pix") -> None:
    """Paga a próxima taxa pendente pela UI e confirma via rota de simulação."""
    page.goto(f"{BASE_URL}/pagamento/inscricao/{protocol}/")
    wait_for_page(page, "Pagamento")
    page.select_option('select[name="method"]', _payment_method_value(method))
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


# ---------------------------------------------------------------------------
# Helpers adicionais (jornada completa, auditoria, backoffice e e-mail)
# ---------------------------------------------------------------------------


def extract_link(text: str, path_fragment: str) -> str:
    """Extrai do corpo do e-mail a URL absoluta que contém ``path_fragment``."""
    match = _re.search(
        rf"https?://[^\s<>\"']*{_re.escape(path_fragment)}[^\s<>\"']*",
        text,
    )
    assert match is not None, f"Link com {path_fragment!r} não encontrado no e-mail."
    return match.group(0).replace("http://web:8000", BASE_URL)


def api_post_json(path: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
    """POST JSON direto na aplicação (usado para o webhook Pix)."""
    request = _urlrequest.Request(
        f"{BASE_URL}{path}",
        data=_json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with _urlrequest.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, _json.loads(body) if body else {}
    except _urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            data = _json.loads(body) if body else {}
        except _json.JSONDecodeError:
            data = {"raw": body}
        return exc.code, data


def api_get_status(path: str) -> int:
    """GET autenticado? Não — usado apenas para URLs públicas/robots."""
    try:
        with _urlrequest.urlopen(f"{BASE_URL}{path}", timeout=15) as response:
            return response.status
    except _urlerror.HTTPError as exc:
        return exc.code


def mail_link(latest_email, to: str, path_fragment: str) -> str:
    """Lê o e-mail mais recente do destinatário e devolve o link solicitado."""
    message = latest_email(to=to)
    return extract_link(message["body"], path_fragment)


def submit_dataset_file(page: Page, protocol: str, filename: str = "dados-e2e.csv") -> None:
    """Candidato envia dados para auditoria por arquivo."""
    page.goto(f"{BASE_URL}/auditoria/inscricao/{protocol}/enviar/")
    page.select_option('select[name="channel"]', "file")
    page.set_input_files('input[name="file"]', {
        "name": filename,
        "mimeType": "text/csv",
        "buffer": b"coluna_a,coluna_b\n1,2\n",
    })
    page.fill('textarea[name="note"]', "Dados enviados pelo E2E.")
    page.click("button[type='submit']")
    wait_for_page(page)


def review_submission_by_protocol(page: Page, protocol: str, outcome: str, note: str = "Revisão E2E") -> None:
    """Encontra a submissão pela fila e registra a revisão do docente."""
    page.goto(f"{BASE_URL}/auditoria/fila/")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    row.locator("a:has-text('Analisar')").click()
    wait_for_page(page)
    review_submission(page, outcome, note)


def schedule_screening_for(page: Page, protocol: str, date_str: str, mode: str = "online") -> None:
    page.goto(f"{BASE_URL}/agendamentos/triagem/{protocol}/")
    expect(page.locator('input[name="scheduled_date"]')).to_be_visible()
    page.fill('input[name="scheduled_date"]', date_str)
    page.fill('input[name="scheduled_time"]', "10:00")
    page.select_option('select[name="meeting_mode"]', mode)
    if mode == "online":
        page.fill('input[name="virtual_link"]', "https://meet.example.com/e2e")
    else:
        page.fill('input[name="place"]', "Sala E2E")
    page.click("button[type='submit']")
    wait_for_page(page)


def schedule_consultation_for(page: Page, protocol: str, date_str: str, mode: str = "online") -> None:
    page.goto(f"{BASE_URL}/agendamentos/reuniao/{protocol}/")
    expect(page.locator('input[name="scheduled_date"]')).to_be_visible()
    page.fill('input[name="scheduled_date"]', date_str)
    page.fill('input[name="scheduled_time"]', "10:00")
    page.select_option('select[name="meeting_mode"]', mode)
    if mode == "online":
        page.fill('input[name="virtual_link"]', "https://meet.example.com/e2e")
    else:
        page.fill('input[name="place"]', "Sala E2E")
    page.click("button[type='submit']")
    wait_for_page(page)


def open_first_screening_decision(page: Page, protocol: str) -> None:
    page.goto(f"{BASE_URL}/triagens/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    row.locator("a[title='Informar Resultado']").first.click()
    wait_for_page(page)


def open_first_consultation_decision(page: Page, protocol: str) -> None:
    page.goto(f"{BASE_URL}/reunioes/?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    row.locator("a[title='Informar Resultado']").first.click()
    wait_for_page(page)


def open_teacher_feedback(page: Page, list_path: str, protocol: str) -> None:
    """Abre a tela de decisão pelo link de feedback do docente."""
    page.goto(f"{BASE_URL}{list_path}?term=all")
    wait_for_page(page)
    row = page.locator("tr", has_text=protocol).first
    expect(row).to_be_visible()
    row.locator("a:has-text('Registrar feedback')").first.click()
    wait_for_page(page)


def assert_status_page(page: Page, protocol: str, text: str) -> None:
    page.goto(f"{BASE_URL}/inscricoes/{protocol}/")
    wait_for_page(page)
    expect(page.locator("body")).to_contain_text(text)


def start_payment(page: Page, protocol: str, method: str = "pix", fee_id: int | None = None) -> None:
    """Gera o instrumento pela UI sem confirmar o pagamento."""
    url = f"{BASE_URL}/pagamento/inscricao/{protocol}/"
    if fee_id is not None:
        url += f"?fee={fee_id}"
    page.goto(url)
    wait_for_page(page, "Pagamento")
    page.select_option('select[name="method"]', _payment_method_value(method))
    page.click("button[type='submit']")
    if method == "pix":
        wait_for_page(page, "Pagamento via Pix")
    else:
        wait_for_page(page, "Pagamento via Boleto")





def select_term(page: Page, label: str) -> None:
    """Seleciona o período letivo pelo rótulo no formulário de inscrição."""
    page.select_option('select[name="term"]', label=label)


def set_application_term(page: Page, term_id: int | str) -> None:
    """Fixa o período enviado pelo formulário (campo oculto ``term``)."""
    field = page.locator('input[name="term"]')
    field.wait_for(state="attached")
    field.evaluate("(element, value) => { element.value = value; }", str(term_id))
