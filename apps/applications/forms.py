from django import forms
from django.forms.models import ModelChoiceIterator

from terms.models import AcademicTerm

from .models import CatalogOption, ServiceApplication
from .validators import validate_br_tax_id

MAX_TOTAL_ATTACHMENT_SIZE = 8 * 1024 * 1024

YES_NO_CHOICES = [("true", "Sim"), ("false", "Não")]

REQUIRED_BANK_FIELDS = [
    "refund_account_holder_name",
    "refund_account_holder_tax_id",
    "refund_bank_name",
    "refund_branch_number",
    "refund_bank_account_number",
    "refund_bank_account_type",
]

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

MENTOR_REQUIRING_PURPOSES = {"undergraduate_research", "master", "doctorate"}


def _yes_no_field(label: str) -> forms.TypedChoiceField:
    return forms.TypedChoiceField(
        choices=YES_NO_CHOICES,
        widget=forms.RadioSelect,
        required=False,
        empty_value=None,
        coerce=lambda value: value == "true",
        label=label,
    )


def _is_other_option(option: CatalogOption) -> bool:
    """Options whose code is 'other' (or label starts with 'Outr') go last."""
    if option.code == "other":
        return True
    return option.label.strip().lower().startswith("outr")


class GroupedCatalogCheckboxSelect(forms.CheckboxSelectMultiple):
    """Checkboxes das opções de catálogo agrupados por categoria."""

    template_name = "applications/widgets/grouped_catalog_select.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if value is None:
            value = []
        if not isinstance(value, (list, tuple)):
            value = [value]
        checked = {str(v) for v in value}

        queryset = self.choices.queryset if isinstance(self.choices, ModelChoiceIterator) else []
        field_id = context["widget"]["attrs"].get("id") or f"id_{name}"

        groups = []
        for category in CatalogOption.Category:
            options = [opt for opt in queryset if opt.category == category.value]
            if not options:
                continue
            options.sort(key=lambda opt: _is_other_option(opt))
            groups.append(
                {
                    "title": category.label,
                    "options": [
                        {
                            "id": f"{field_id}_{opt.pk}",
                            "name": name,
                            "value": opt.pk,
                            "label": opt.label,
                            "checked": str(opt.pk) in checked,
                            "is_other": _is_other_option(opt),
                        }
                        for opt in options
                    ],
                }
            )
        context["groups"] = groups
        return context


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, "getlist"):
            return files.getlist(name)
        value = files.get(name)
        if value is None:
            return []
        return value if isinstance(value, (list, tuple)) else [value]


class MultipleFileField(forms.Field):
    widget = MultipleFileInput

    def to_python(self, data):
        if not data:
            return []
        return data

    def validate(self, value) -> None:
        if value in self.empty_values and self.required:
            raise forms.ValidationError(self.error_messages["required"], code="required")
        for upload in value:
            if not hasattr(upload, "size"):
                raise forms.ValidationError(self.error_messages["invalid"], code="invalid")


class ApplicationForm(forms.Form):
    term = forms.ModelChoiceField(queryset=AcademicTerm.objects.all(), label="Período letivo")
    modality = forms.ChoiceField(
        choices=ServiceApplication.Modality.choices,
        widget=forms.RadioSelect,
        label="Modalidade",
    )
    researcher_name = forms.CharField(max_length=255, label="Nome do pesquisador")
    contact_email = forms.EmailField(max_length=255, label="E-mail de contato")
    contact_email_confirmation = forms.EmailField(max_length=255, required=False, label="Repetir e-mail")
    contact_phone = forms.CharField(max_length=50, required=False, label="Telefones para contato")
    has_whatsapp = forms.BooleanField(required=False, label="WhatsApp")
    tax_id = forms.CharField(max_length=20, required=False, label="CPF/CNPJ")
    institution_name = forms.CharField(max_length=255, required=False, label="Instituição/Unidade")
    course_name = forms.CharField(max_length=255, required=False, label="Curso")
    mentor_name = forms.CharField(max_length=255, required=False, label="Colaborador(es) ou orientador")
    catalog_options = forms.ModelMultipleChoiceField(
        queryset=CatalogOption.objects.filter(is_active=True),
        required=False,
        label="Seleções",
        widget=GroupedCatalogCheckboxSelect,
    )
    catalog_other_text = forms.CharField(max_length=255, required=False, label="Descreva 'Outro'")
    attachments = MultipleFileField(
        required=False,
        label="Anexos",
        widget=MultipleFileInput(attrs={"multiple": True}),
    )

    project_title = forms.CharField(max_length=255, required=False, label="Título do projeto")
    context_summary = forms.CharField(widget=forms.Textarea, required=False, label="Aspectos gerais")
    general_objectives = forms.CharField(widget=forms.Textarea, required=False, label="Objetivos gerais")
    variables_and_measurements = forms.CharField(
        widget=forms.Textarea, required=False, label="Características e variáveis"
    )
    contextual_factors = forms.CharField(
        widget=forms.Textarea, required=False, label="Outras características relevantes"
    )
    sampling_and_limitations = forms.CharField(
        widget=forms.Textarea, required=False, label="Amostra, restrições e limitações"
    )
    data_management_plan = forms.CharField(widget=forms.Textarea, required=False, label="Armazenamento dos dados")
    expected_results = forms.CharField(widget=forms.Textarea, required=False, label="Conclusões esperadas")
    expected_support = forms.CharField(widget=forms.Textarea, required=False, label="Ajuda esperada do CEA")
    data_already_collected = _yes_no_field("Os dados já foram coletados")
    data_use_authorization_accepted = forms.BooleanField(
        required=False,
        label="Autorizo a utilização dos dados para fins didáticos e/ou ilustração de métodos "
        "estatísticos em artigos científicos, desde que sejam apresentados em simpósios ou "
        "publicações com maior concentração na área de Estatística. Em qualquer circunstância, "
        "a fonte será citada explicitamente.",
    )
    mentor_declaration_accepted = forms.BooleanField(
        required=False,
        label="Declaro que estou ciente de que o(a) meu/minha orientador(a) deverá estar presente na entrevista.",
    )

    wants_refund_receipt = _yes_no_field("Recibo para reembolso")
    refund_receipt_details = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Dados que devem constar no recibo",
    )
    refund_account_holder_name = forms.CharField(max_length=255, required=False, label="Nome completo")
    refund_account_holder_tax_id = forms.CharField(max_length=20, required=False, label="CPF/CNPJ (dados bancários)")
    refund_bank_name = forms.CharField(max_length=255, required=False, label="Nome do banco")
    refund_branch_number = forms.CharField(max_length=50, required=False, label="Número da agência (sem DV)")
    refund_bank_account_number = forms.CharField(max_length=50, required=False, label="Número da conta")
    refund_bank_account_type = forms.ChoiceField(
        choices=[("checking", "Conta Corrente"), ("savings", "Poupança")],
        widget=forms.RadioSelect,
        required=False,
        label="Tipo da Conta",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""
        if not self.is_bound:
            latest_term = AcademicTerm.objects.first()
            if latest_term:
                self.fields["term"].initial = latest_term

    def clean_tax_id(self):
        value = self.cleaned_data.get("tax_id")
        if value:
            return validate_br_tax_id(value)
        return None

    def clean_contact_email_confirmation(self):
        email = self.cleaned_data.get("contact_email")
        confirmation = self.cleaned_data.get("contact_email_confirmation")
        if email and confirmation and confirmation != email:
            raise forms.ValidationError("Os e-mails não conferem.")
        return confirmation

    def clean_refund_account_holder_tax_id(self):
        value = self.cleaned_data.get("refund_account_holder_tax_id")
        if value:
            return validate_br_tax_id(value)
        return None

    def clean_attachments(self):
        files = self.cleaned_data.get("attachments") or []
        total = sum(upload.size for upload in files)
        if total > MAX_TOTAL_ATTACHMENT_SIZE:
            raise forms.ValidationError("O total de anexos excede o limite de 8 MB.")
        return files

    def clean(self):
        cleaned_data = super().clean() or {}
        modality = cleaned_data.get("modality")
        catalog_options = cleaned_data.get("catalog_options") or []

        if not cleaned_data.get("data_use_authorization_accepted"):
            self.add_error(
                "data_use_authorization_accepted",
                "A autorização de uso dos dados é obrigatória.",
            )

        by_category: dict[str, list] = {}
        for option in catalog_options:
            by_category.setdefault(option.category, []).append(option)
        for _category, opts in by_category.items():
            if len(opts) > 1:
                self.add_error(
                    "catalog_options",
                    "Selecione apenas uma opção por seção.",
                )
                break
        other_text = cleaned_data.get("catalog_other_text")
        has_other = any(option.code == "other" for option in catalog_options)
        if has_other and not other_text:
            self.add_error(
                "catalog_other_text",
                "Informe o texto complementar para a opção 'Outro'.",
            )

        if modality == ServiceApplication.Modality.PROJECT:
            if not cleaned_data.get("data_already_collected"):
                self.add_error(
                    "data_already_collected",
                    "Para solicitar assessoria em Projeto é necessário já ter coletado os dados.",
                )
            for field_name in PROJECT_DESCRIPTIVE_FIELDS:
                if not (cleaned_data.get(field_name) or "").strip():
                    self.add_error(
                        field_name,
                        "Este campo é obrigatório para inscrições de Projeto.",
                    )

        purposes = {
            option.code for option in catalog_options if option.category == CatalogOption.Category.PROJECT_PURPOSE
        }
        if purposes & MENTOR_REQUIRING_PURPOSES:
            if not (cleaned_data.get("mentor_name") or "").strip():
                self.add_error(
                    "mentor_name",
                    "Informe o nome do orientador.",
                )
            if not cleaned_data.get("mentor_declaration_accepted"):
                self.add_error(
                    "mentor_declaration_accepted",
                    "A declaração de presença do orientador é obrigatória.",
                )

        if cleaned_data.get("wants_refund_receipt"):
            for field_name in REQUIRED_BANK_FIELDS + ["refund_receipt_details"]:
                if not cleaned_data.get(field_name):
                    self.add_error(
                        field_name,
                        "Este campo é obrigatório quando há recibo de reembolso.",
                    )
        return cleaned_data
