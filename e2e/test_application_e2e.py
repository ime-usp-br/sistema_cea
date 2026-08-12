"""Testes E2E de navegador para o formulário de inscrição (Playwright + pytest).

Cenários:
  E2E_001 - Submissão válida de Projeto -> redireciona para o detalhe.
  E2E_002 - Submissão válida de Consulta -> detalhe com status "Aguardando pagamento".
  E2E_003 - Submissão de Projeto vazio -> resumo de erro aparece e impede envio.
  E2E_004 - Projeto com "Dados coletados = Não" -> mensagem de bloqueio é exibida.
  E2E_005 - Catálogo "Outro" -> campo complementar aparece e torna-se obrigatório.
  E2E_006 - Iniciação Científica/Mestrado -> orientador e declaração exigidos.
"""

from __future__ import annotations

import re

from helpers import (
    BASE_URL,
    fill_required_basic_fields,
    fill_valid_consultation,
    fill_valid_project,
    select_catalog_option,
)
from playwright.sync_api import Page, expect

DETAIL_PATH_RE = re.compile(r"/inscricoes/\d{9}/$")


def _go_to_new_application(page: Page) -> None:
    page.goto(f"{BASE_URL}/inscricoes/nova/")
    page.wait_for_load_state("networkidle")
    expect(page.locator("#form-inscricao")).to_be_visible()


# ---------------------------------------------------------------------------
# E2E_001 / E2E_002 — Submissões válidas
# ---------------------------------------------------------------------------


def test_E2E_001_submissao_valida_de_projeto_redireciona_ao_detalhe(
    login, page: Page
) -> None:
    login()
    _go_to_new_application(page)

    fill_valid_project(page)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(re.compile(r".*" + DETAIL_PATH_RE.pattern))
    expect(page.locator("h1.page-title")).to_contain_text("Inscrição")
    expect(page.locator("body")).to_contain_text("Aguardando envio de dados")


def test_E2E_002_submissao_valida_de_consulta_aguarda_pagamento(
    login, page: Page
) -> None:
    login()
    _go_to_new_application(page)

    fill_valid_consultation(page)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(re.compile(r".*" + DETAIL_PATH_RE.pattern))
    expect(page.locator("h1.page-title")).to_contain_text("Inscrição")
    expect(page.locator("body")).to_contain_text("Aguardando pagamento")


# ---------------------------------------------------------------------------
# E2E_003 / E2E_004 — Validações interativas (frontend)
# ---------------------------------------------------------------------------


def test_E2E_003_projeto_vazio_mostra_resumo_de_erro_e_nao_envia(
    login, page: Page
) -> None:
    login()
    _go_to_new_application(page)

    page.click("button[type='submit']")

    summary = page.locator("#form-error-summary")
    expect(summary).to_be_visible()
    expect(summary).to_contain_text("campos para corrigir")
    expect(page.locator(".js-error").first).to_be_visible()
    # O formulário não deve ter navegado (envio bloqueado pela validação).
    expect(page).to_have_url(re.compile(r".*inscricoes/nova/"))


def test_E2E_004_projeto_com_dados_nao_coletados_exibe_bloqueio(
    login, page: Page
) -> None:
    login()
    _go_to_new_application(page)

    page.check('input[name="modality"][value="project"]')
    page.check('input[name="data_already_collected"][value="false"]')

    expect(page.locator("body")).to_contain_text(
        "Para solicitar assessoria em Projeto é necessário já ter coletado os dados."
    )


# ---------------------------------------------------------------------------
# E2E_005 / E2E_006 — Regras condicionais do catálogo
# ---------------------------------------------------------------------------


def test_E2E_005_catalogo_outro_exibe_campo_complementar_e_exige_preenchimento(
    login, page: Page
) -> None:
    login()
    _go_to_new_application(page)
    page.check('input[name="modality"][value="consultation"]')
    fill_required_basic_fields(page)

    select_catalog_option(page, "other", category="institutional_tie")

    other_field = page.locator("#id_catalog_other_text")
    expect(other_field).to_be_visible()

    # Sem preencher o texto complementar, o envio deve ser bloqueado com erro.
    page.click("button[type='submit']")
    expect(page.locator("body")).to_contain_text("Informe o texto complementar")


def test_E2E_006_iniciacao_cientifica_exige_orientador_e_declaracao(
    login, page: Page
) -> None:
    login()
    _go_to_new_application(page)

    select_catalog_option(page, "undergraduate_research")

    expect(page.locator("body")).to_contain_text("Informe o nome do orientador.")
    expect(page.locator("body")).to_contain_text(
        "A declaração de presença do orientador é obrigatória."
    )


def test_E2E_006b_mestrado_exige_orientador_e_declaracao(
    login, page: Page
) -> None:
    login()
    _go_to_new_application(page)

    select_catalog_option(page, "master")

    expect(page.locator("body")).to_contain_text("Informe o nome do orientador.")
    expect(page.locator("body")).to_contain_text(
        "A declaração de presença do orientador é obrigatória."
    )
