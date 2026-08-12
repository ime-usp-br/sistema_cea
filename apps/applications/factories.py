import random
from typing import Any

import factory

from base.factories import fake_br
from terms.factories import AcademicTermFactory
from users.factories import UserFactory

from .models import CatalogOption, ServiceApplication
from .services import ApplicationSubmissionService

# ---------------------------------------------------------------------------
# Calibração a partir de inscrições históricas
# ---------------------------------------------------------------------------
# Os campos "tipo catálogo" eram texto livre, mas os valores dominantes
# coincidem exatamente com as opções semeadas no novo sistema. As tuplas
# abaixo carregam (code, peso) com base nas frequências observadas.
_CATALOG_WEIGHTS: dict[str, list[tuple[str, int]]] = {
    CatalogOption.Category.INSTITUTIONAL_TIE: [
        ("student", 52),  # Estudante
        ("other", 16),  # Outro
        ("staff", 8),  # Funcionário
        ("faculty", 7),  # Professor
    ],
    CatalogOption.Category.PROJECT_PURPOSE: [
        ("doctorate", 57),  # Doutorado
        ("master", 42),  # Mestrado
        ("publication", 28),  # Publicação
        ("other", 25),  # Outra
        ("undergraduate_research", 7),  # Iniciação Científica
    ],
    CatalogOption.Category.FUNDING_AGENCY: [
        ("other", 80),  # Outra
        ("fapesp", 19),  # FAPESP
        ("cnpq", 14),  # CNPq
    ],
    CatalogOption.Category.KNOWLEDGE_AREA: [
        ("health_biological", 87),  # Médica ou Biológica
        ("social_human", 36),  # Social ou Humana
        ("other", 17),  # Outra
        ("technological", 11),  # Tecnológica
        ("economic", 6),  # Econômica
    ],
}

_REFUND_BANKS = ["Banco do Brasil", "Itaú", "Bradesco", "Caixa Econômica", "Santander"]


def _pick_catalog_option_ids(faker) -> tuple[list[str], bool]:
    """Escolhe uma opção ativa por seção com pesos reais.

    Retorna (pks escolhidos, usou_opcao_outro).
    """
    picked: list[str] = []
    used_other = False
    for category, weighted in _CATALOG_WEIGHTS.items():
        codes = [code for code, _ in weighted]
        weights = [weight for _, weight in weighted]
        code = faker.random.choices(codes, weights=weights, k=1)[0]
        option = CatalogOption.objects.get(category=category, code=code)
        picked.append(str(option.pk))
        if code == "other":
            used_other = True
    return picked, used_other


def _random_modality() -> str:
    # Apenas 12 aplicações tinham modalidade definida (8 Consulta, 4 Projeto).
    return fake_br.random.choices(
        [ServiceApplication.Modality.PROJECT, ServiceApplication.Modality.CONSULTATION],
        weights=[4, 8],
        k=1,
    )[0]


def build_valid_form_payload(
    *,
    modality: str = ServiceApplication.Modality.PROJECT,
    term_pk: int,
    catalog_required: bool = True,
    **overrides: Any,
) -> dict[str, Any]:
    """Monta um payload de POST 100% válido para o ApplicationForm.

    Uso em testes de formulário via ``Client.post(reverse("applications:create"), payload)``.
    Qualquer campo pode ser sobrescrito via ``**overrides`` (ex.: trocar por dado
    inválido para testar rejeição).
    """
    email = fake_br.email()
    catalog_option_ids, used_other = _pick_catalog_option_ids(fake_br) if catalog_required else ([], False)

    wants_refund_receipt = fake_br.random.choices(["false", "true"], weights=[10, 2], k=1)[0]
    data_collected = fake_br.random.choices(["true", "false"], weights=[10, 2], k=1)[0]
    has_whatsapp = fake_br.random.choices(["on", ""], weights=[4, 8], k=1)[0]

    payload: dict[str, Any] = {
        "term": str(term_pk),
        "modality": modality,
        "researcher_name": fake_br.name(),
        "contact_email": email,
        "contact_email_confirmation": email,
        "contact_phone": fake_br.phone_number(),
        "has_whatsapp": has_whatsapp,
        "tax_id": fake_br.cpf(),
        "institution_name": fake_br.company(),
        "course_name": fake_br.job(),
        "mentor_name": fake_br.name(),
        "data_already_collected": data_collected,
        "data_use_authorization_accepted": "on",
        "mentor_declaration_accepted": "on",
        "catalog_other_text": fake_br.sentence(nb_words=6) if used_other else "",
    }
    if catalog_required:
        payload["catalog_options"] = catalog_option_ids

    if modality == ServiceApplication.Modality.PROJECT:
        payload.update(
            {
                "project_title": fake_br.sentence(nb_words=8),
                "context_summary": fake_br.paragraph(nb_sentences=5),
                "general_objectives": fake_br.paragraph(nb_sentences=4),
                "variables_and_measurements": fake_br.paragraph(nb_sentences=4),
                "contextual_factors": fake_br.paragraph(nb_sentences=3),
                "sampling_and_limitations": fake_br.paragraph(nb_sentences=3),
                "data_management_plan": fake_br.paragraph(nb_sentences=3),
                "expected_results": fake_br.paragraph(nb_sentences=3),
                "expected_support": fake_br.paragraph(nb_sentences=2),
            }
        )

    if wants_refund_receipt == "true":
        payload.update(
            {
                "wants_refund_receipt": "true",
                "refund_receipt_details": fake_br.sentence(nb_words=10),
                "refund_account_holder_name": fake_br.name(),
                "refund_account_holder_tax_id": fake_br.cpf(),
                "refund_bank_name": fake_br.random_element(_REFUND_BANKS),
                "refund_branch_number": fake_br.random_int(1, 9999),
                "refund_bank_account_number": fake_br.random_int(1, 99999),
                "refund_bank_account_type": fake_br.random.choices(
                    ["checking", "savings"], weights=[163, 5], k=1
                )[0],
            }
        )

    payload.update(overrides)
    return payload


class ApplicationFormPayloadFactory(factory.Factory):
    """Factory que gera um dicionário de POST válido para o ApplicationForm.

    Obs.: campos com prefixo ``refund_`` só entram quando o recibo é desejado.
    """

    class Meta:
        abstract = True

    term = factory.LazyAttribute(lambda o: o.term_pk)
    modality = factory.LazyAttribute(lambda o: o.modality)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        modality = kwargs.pop("modality")
        term_pk = kwargs.pop("term_pk")
        return build_valid_form_payload(modality=modality, term_pk=term_pk, **kwargs)


def service_kwargs_from_payload(payload: dict[str, Any], term: Any) -> dict[str, Any]:
    """Traduz um payload de formulário para os kwargs do ApplicationSubmissionService."""
    return {
        "term": term,
        "modality": payload["modality"],
        "researcher_name": payload["researcher_name"],
        "contact_email": payload["contact_email"],
        "contact_phone": payload.get("contact_phone"),
        "has_whatsapp": payload.get("has_whatsapp") == "on",
        "tax_id": payload.get("tax_id"),
        "institution_name": payload.get("institution_name"),
        "course_name": payload.get("course_name"),
        "mentor_name": payload.get("mentor_name"),
        "project_title": payload.get("project_title"),
        "context_summary": payload.get("context_summary"),
        "general_objectives": payload.get("general_objectives"),
        "variables_and_measurements": payload.get("variables_and_measurements"),
        "contextual_factors": payload.get("contextual_factors"),
        "sampling_and_limitations": payload.get("sampling_and_limitations"),
        "data_management_plan": payload.get("data_management_plan"),
        "expected_results": payload.get("expected_results"),
        "expected_support": payload.get("expected_support"),
        "data_already_collected": payload.get("data_already_collected") == "true",
        "data_use_authorization_accepted": payload.get("data_use_authorization_accepted") == "on",
        "mentor_declaration_accepted": payload.get("mentor_declaration_accepted") == "on",
        "wants_refund_receipt": payload.get("wants_refund_receipt") == "true",
        "refund_receipt_details": payload.get("refund_receipt_details"),
        "refund_account_holder_name": payload.get("refund_account_holder_name"),
        "refund_account_holder_tax_id": payload.get("refund_account_holder_tax_id"),
        "refund_bank_name": payload.get("refund_bank_name"),
        "refund_branch_number": payload.get("refund_branch_number"),
        "refund_bank_account_number": payload.get("refund_bank_account_number"),
        "refund_bank_account_type": payload.get("refund_bank_account_type"),
        "catalog_option_ids": [int(pk) for pk in payload.get("catalog_options", [])],
        "catalog_other_text": payload.get("catalog_other_text"),
    }


class ApplicationFactory(factory.Factory):
    """Cria inscrições válidas percorrendo o Service Layer (fluxo real).

    NÃO insere direto no model: passa pelo ApplicationSubmissionService para
    respeitar a máquina de estados, gerar eventos e (em Consulta) criar a taxa.
    """

    class Meta:
        model = ServiceApplication

    term = factory.SubFactory(AcademicTermFactory)
    owner = factory.SubFactory(UserFactory)
    modality = factory.LazyFunction(_random_modality)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        term = kwargs.pop("term")
        owner = kwargs.pop("owner")
        modality = kwargs.pop("modality")
        catalog_ids, _used = _pick_catalog_option_ids(fake_br)
        service = ApplicationSubmissionService()
        return service.create_application(
            term=term,
            owner=owner,
            modality=modality,
            researcher_name=fake_br.name(),
            contact_email=fake_br.email(),
            contact_phone=fake_br.phone_number(),
            has_whatsapp=random.choice([True, False]),
            tax_id=fake_br.cpf(),
            institution_name=fake_br.company(),
            mentor_name=fake_br.name(),
            catalog_option_ids=[int(pk) for pk in catalog_ids],
            **kwargs,
        )


__all__ = [
    "ApplicationFactory",
    "ApplicationFormPayloadFactory",
    "build_valid_form_payload",
    "service_kwargs_from_payload",
]
