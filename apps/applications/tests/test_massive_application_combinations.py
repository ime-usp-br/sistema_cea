"""Suíte massiva e combinatória do formulário de inscrição.

Traduz as matrizes de teste da Seção 2 de
``docs/APPLICATION_VALIDATION_AND_TESTS.md`` para ``@pytest.mark.parametrize``,
garantindo que o ``ApplicationForm`` replique rigorosamente as regras de
validação do formulário de referência.

POLÍTICA DE ANONIMIZAÇÃO:
Nenhum dado pessoal é copiado para esta suíte. Todos os payloads são gerados
com ``fake_br`` (Faker com semente fixa) — nomes, e-mails, telefones e
CPF/CNPJ são sintéticos. São aproveitadas APENAS características estruturais
e anônimas: distribuição de modalidades, frequência das opções de catálogo e
traços booleanos (coleta de dados, recibo de reembolso), conforme calibração
já documentada em ``apps/applications/factories.py``.

Matrizes cobertas:
- 2.1 Modalidade e validações cruzadas (Projeto vs Consulta).
- 1.5 Catálogo de opções ("Outro" e máximo de uma opção por seção).
- 2.2 Dados bancários / reembolso.
- 2.3 Regressão com amostragem representativa (dados 100% sintéticos).
"""

from typing import Any

import pytest
from django.urls import reverse

from applications.factories import build_valid_form_payload
from applications.forms import ApplicationForm
from applications.models import CatalogOption, ServiceApplication
from base.factories import fake_br
from terms.factories import AcademicTermFactory
from users.factories import UserFactory

PROJECT_DESCRIPTIVE_FIELDS = [
    "project_title",
    "context_summary",
    "general_objectives",
    "variables_and_measurements",
    "contextual_factors",
    "sampling_and_limitations",
    "data_management_plan",
    "expected_results",
    "expected_support",
]

BANK_FIELDS = [
    "refund_account_holder_name",
    "refund_account_holder_tax_id",
    "refund_bank_name",
    "refund_branch_number",
    "refund_bank_account_number",
    "refund_bank_account_type",
]

MENTOR_PURPOSES = ["undergraduate_research", "master", "doctorate"]

CATALOG_CATEGORIES = [
    "institutional_tie",
    "project_purpose",
    "knowledge_area",
    "funding_agency",
]

# Amostra de combinações representativas de inscrições, respeitando a
# distribuição calibrada em ``apps/applications/factories.py``
# (8 Consulta : 4 Projeto). Contém apenas atributos estruturais ANÔNIMOS —
# os valores pessoais são sempre sintéticos (Faker).
# Formato: (modality, project_purpose, data_already_collected, wants_refund_receipt)
SAMPLE_RECIPES = [
    ("consultation", "publication", "false", False),
    ("consultation", "doctorate", "true", True),
    ("consultation", "master", "false", False),
    ("consultation", "undergraduate_research", "true", False),
    ("consultation", "other", "false", True),
    ("project", "doctorate", "true", True),
    ("project", "master", "true", False),
    ("project", "undergraduate_research", "true", False),
    ("project", "publication", "true", True),
    ("project", "other", "true", False),
]


@pytest.fixture
def term(db):
    return AcademicTermFactory()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def logged_client(client, user):
    client.force_login(user)
    return client


def _force_catalog_purpose(payload: dict[str, Any], purpose_code: str) -> dict[str, Any]:
    """Substitui a finalidade do projeto selecionada por ``purpose_code``."""
    purpose = CatalogOption.objects.get(
        category=CatalogOption.Category.PROJECT_PURPOSE,
        code=purpose_code,
    )
    selected_ids = [int(pk) for pk in payload.get("catalog_options", [])]
    selected = CatalogOption.objects.filter(pk__in=selected_ids)
    new_ids = [str(opt.pk) for opt in selected if opt.category != CatalogOption.Category.PROJECT_PURPOSE]
    new_ids.append(str(purpose.pk))
    payload["catalog_options"] = new_ids
    return payload


def _fill_refund(payload: dict[str, Any]) -> dict[str, Any]:
    payload["wants_refund_receipt"] = "true"
    payload["refund_receipt_details"] = "Recibo em nome do pesquisador"
    payload["refund_account_holder_name"] = fake_br.name()
    payload["refund_account_holder_tax_id"] = fake_br.cpf()
    payload["refund_bank_name"] = "Banco do Brasil"
    payload["refund_branch_number"] = "1234"
    payload["refund_bank_account_number"] = "56789-0"
    payload["refund_bank_account_type"] = "checking"
    return payload


def _clear_refund(payload: dict[str, Any]) -> dict[str, Any]:
    payload["wants_refund_receipt"] = "false"
    for field_name in BANK_FIELDS + ["refund_receipt_details"]:
        payload.pop(field_name, None)
    return payload


def _build_sampled_payload(
    term_pk: int,
    modality: str,
    purpose_code: str,
    data_collected: str,
    refund: bool,
) -> dict[str, Any]:
    payload = build_valid_form_payload(modality=modality, term_pk=term_pk)
    payload["data_already_collected"] = data_collected
    _force_catalog_purpose(payload, purpose_code)
    if purpose_code == "other":
        payload["catalog_other_text"] = "Finalidade diversa"
    if refund:
        _fill_refund(payload)
    else:
        _clear_refund(payload)
    return payload


def _response_form_errors(response) -> str:
    if response.status_code == 302:
        return "redirecionado com sucesso"
    if response.context is not None:
        form = response.context.get("form")
        if form is not None:
            return str(dict(form.errors))
    return f"status {response.status_code}"


@pytest.mark.django_db
class TestModalityMatrix:
    """Matriz 2.1 — Projeto vs Consulta e validações cruzadas."""

    def test_TS_APP_011_projeto_valido_completo_passa(self, term) -> None:
        payload = build_valid_form_payload(modality="project", term_pk=term.pk)
        payload["data_already_collected"] = "true"
        form = ApplicationForm(data=payload)
        assert form.is_valid(), form.errors

    @pytest.mark.parametrize("collected", ["false", "", None])
    def test_TS_APP_012_projeto_dados_nao_coletados_falha(self, term, collected) -> None:
        payload = build_valid_form_payload(modality="project", term_pk=term.pk)
        payload["data_already_collected"] = collected
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "data_already_collected" in form.errors

    @pytest.mark.parametrize("field_name", PROJECT_DESCRIPTIVE_FIELDS)
    def test_TS_APP_013_projeto_falta_campo_descritivo_falha(self, term, field_name) -> None:
        payload = build_valid_form_payload(modality="project", term_pk=term.pk)
        payload["data_already_collected"] = "true"
        payload[field_name] = ""
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert field_name in form.errors

    @pytest.mark.parametrize("purpose_code", MENTOR_PURPOSES)
    def test_TS_APP_014_projeto_sem_nome_orientador_falha(self, term, purpose_code) -> None:
        payload = _force_catalog_purpose(
            build_valid_form_payload(modality="project", term_pk=term.pk),
            purpose_code,
        )
        payload["data_already_collected"] = "true"
        payload["mentor_name"] = ""
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "mentor_name" in form.errors

    @pytest.mark.parametrize("purpose_code", MENTOR_PURPOSES)
    def test_TS_APP_014_projeto_sem_declaracao_orientador_falha(self, term, purpose_code) -> None:
        payload = _force_catalog_purpose(
            build_valid_form_payload(modality="project", term_pk=term.pk),
            purpose_code,
        )
        payload["data_already_collected"] = "true"
        payload["mentor_declaration_accepted"] = ""
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "mentor_declaration_accepted" in form.errors

    @pytest.mark.parametrize("purpose_code", ["publication", "livre_docencia", "other"])
    def test_TS_APP_014_sem_finalidade_academica_nao_exige_mentor_passa(self, term, purpose_code) -> None:
        payload = _force_catalog_purpose(
            build_valid_form_payload(modality="project", term_pk=term.pk),
            purpose_code,
        )
        payload["data_already_collected"] = "true"
        if purpose_code == "other":
            payload["catalog_other_text"] = "Finalidade diversa"
        payload["mentor_name"] = ""
        payload["mentor_declaration_accepted"] = ""
        form = ApplicationForm(data=payload)
        assert form.is_valid(), form.errors

    def test_TS_APP_015_consulta_valida_completa_passa(self, term) -> None:
        payload = build_valid_form_payload(modality="consultation", term_pk=term.pk)
        form = ApplicationForm(data=payload)
        assert form.is_valid(), form.errors

    def test_TS_APP_016_consulta_sem_autorizacao_dados_falha(self, term) -> None:
        payload = build_valid_form_payload(modality="consultation", term_pk=term.pk)
        payload["data_use_authorization_accepted"] = ""
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "data_use_authorization_accepted" in form.errors


@pytest.mark.django_db
class TestCatalogOptionsMatrix:
    """Seção 1.5 — Catálogo de opções e campo "Outro"."""

    @pytest.mark.parametrize("category", CATALOG_CATEGORIES)
    def test_TS_APP_007_outro_exige_texto_complementar_falha(self, term, category) -> None:
        other = CatalogOption.objects.get(category=category, code="other")
        payload = build_valid_form_payload(
            modality="consultation",
            term_pk=term.pk,
            catalog_options=[str(other.pk)],
            catalog_other_text="",
        )
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "catalog_other_text" in form.errors

    def test_TS_APP_007_outro_com_texto_complementar_passa(self, term) -> None:
        other = CatalogOption.objects.get(category="institutional_tie", code="other")
        payload = build_valid_form_payload(
            modality="consultation",
            term_pk=term.pk,
            catalog_options=[str(other.pk)],
            catalog_other_text="Vínculo externo à USP",
        )
        form = ApplicationForm(data=payload)
        assert form.is_valid(), form.errors

    def test_TS_APP_007_sem_opcao_outro_nao_exige_texto_passa(self, term) -> None:
        publication = CatalogOption.objects.get(
            category="project_purpose",
            code="publication",
        )
        payload = build_valid_form_payload(
            modality="consultation",
            term_pk=term.pk,
            catalog_options=[str(publication.pk)],
            catalog_other_text="",
        )
        form = ApplicationForm(data=payload)
        assert form.is_valid(), form.errors

    @pytest.mark.parametrize("category", CATALOG_CATEGORIES)
    def test_TS_APP_005_maximo_uma_opcao_por_secao_falha(self, term, category) -> None:
        options = list(CatalogOption.objects.filter(category=category).order_by("pk")[:2])
        payload = build_valid_form_payload(
            modality="consultation",
            term_pk=term.pk,
            catalog_options=[str(option.pk) for option in options],
            catalog_other_text="",
        )
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "catalog_options" in form.errors


@pytest.mark.django_db
class TestRefundMatrix:
    """Matriz 2.2 — Dados bancários / reembolso."""

    def test_TS_APP_017_reembolso_completo_passa(self, term) -> None:
        payload = _fill_refund(build_valid_form_payload(modality="consultation", term_pk=term.pk))
        form = ApplicationForm(data=payload)
        assert form.is_valid(), form.errors

    @pytest.mark.parametrize("field_name", BANK_FIELDS)
    def test_TS_APP_018_reembolso_omitindo_campo_bancario_falha(self, term, field_name) -> None:
        payload = _fill_refund(build_valid_form_payload(modality="consultation", term_pk=term.pk))
        payload[field_name] = ""
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert field_name in form.errors

    def test_TS_APP_018_reembolso_omitindo_detalhes_recibo_falha(self, term) -> None:
        payload = _fill_refund(build_valid_form_payload(modality="consultation", term_pk=term.pk))
        payload["refund_receipt_details"] = ""
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "refund_receipt_details" in form.errors

    def test_TS_APP_019_cpf_bancario_invalido_falha(self, term) -> None:
        payload = _fill_refund(build_valid_form_payload(modality="consultation", term_pk=term.pk))
        payload["refund_account_holder_tax_id"] = "111.111.111-11"
        form = ApplicationForm(data=payload)
        assert not form.is_valid()
        assert "refund_account_holder_tax_id" in form.errors

    def test_TS_APP_020_sem_reembolso_dados_bancarios_vazios_passa(self, term) -> None:
        payload = build_valid_form_payload(modality="consultation", term_pk=term.pk)
        payload["wants_refund_receipt"] = "false"
        for field_name in BANK_FIELDS + ["refund_receipt_details"]:
            payload[field_name] = ""
        form = ApplicationForm(data=payload)
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestRegressionSampleMatrix:
    """Matriz 2.3 — Regressão com amostragem representativa."""

    @pytest.mark.parametrize(
        "modality,purpose_code,data_collected,refund",
        SAMPLE_RECIPES,
    )
    def test_TS_APP_022_regressao_payload_representativo_aceito(
        self,
        logged_client,
        term,
        modality,
        purpose_code,
        data_collected,
        refund,
    ) -> None:
        payload = _build_sampled_payload(term.pk, modality, purpose_code, data_collected, refund)
        response = logged_client.post(reverse("applications:create"), payload)
        assert response.status_code == 302, _response_form_errors(response)

    def test_integracao_projeto_sem_dados_coletados_rejeitado(self, logged_client, term) -> None:
        payload = build_valid_form_payload(modality="project", term_pk=term.pk)
        payload["data_already_collected"] = "false"
        response = logged_client.post(reverse("applications:create"), payload)
        assert response.status_code == 200
        assert "data_already_collected" in response.context["form"].errors
        assert ServiceApplication.objects.count() == 0
