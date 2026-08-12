# ESPECIFICAÇÃO DE VALIDAÇÕES E MATRIZ DE TESTES DE INSCRIÇÃO

## 1. Regras de Validação do Formulário (`apps/applications/forms.py`)

O formulário de inscrição (`ApplicationForm`) deve aplicar estritamente as regras de negócio do CEA na sua etapa de validação (`clean()`):

### 1.1 Regras Gerais (Todas as Modalidades)
- `researcher_name`, `contact_email`, `contact_phone`, `tax_id`, `institution_name` e `term` são obrigatórios.
- `data_use_authorization_accepted` (Autorização de uso de dados para fins didáticos/científicos) **deve ser obrigatoriamente Marcado (True)**.
- Se `contact_email` e `contact_email_confirmation` forem informados, devem ser idênticos.
- `tax_id` (CPF/CNPJ) e `refund_account_holder_tax_id` devem passar na validação de dígitos verificadores (`validate_br_tax_id`).

### 1.2 Regras Específicas da Modalidade "Projeto" (`modality == 'project'`)
- **Coleta de dados:** `data_already_collected` deve ser obrigatoriamente `True` ("Sim"). Se for `False` ou não informado, o formulário deve retornar erro: *"Para solicitar assessoria em Projeto é necessário já ter coletado os dados."*
- **Campos Descritivos do Projeto (Itens 1 a 9):** Todos os campos abaixo tornam-se **OBRIGATÓRIOS**:
  - `project_title`
  - `context_summary`
  - `general_objectives`
  - `variables_and_measurements`
  - `contextual_factors`
  - `sampling_and_limitations`
  - `data_management_plan`
  - `expected_results`
  - `expected_support`

### 1.3 Regras Condicionais de Orientador e Declaração
- Se nas seleções do catálogo (`catalog_options`) houver opções de finalidade do projeto (`project_purpose`) equivalentes a **Iniciação Científica** (`undergraduate_research`), **Mestrado** (`master`) ou **Doutorado** (`doctorate`):
  - `mentor_name` torna-se **OBRIGATÓRIO**.
  - `mentor_declaration_accepted` (Declaração de presença do orientador na entrevista) torna-se **OBRIGATÓRIO (True)**.

### 1.4 Regras de Recibo e Dados Bancários de Reembolso
- Se `wants_refund_receipt` for `True`:
  - `refund_receipt_details` é OBRIGATÓRIO.
  - `refund_account_holder_name` é OBRIGATÓRIO.
  - `refund_account_holder_tax_id` é OBRIGATÓRIO (e deve ser CPF/CNPJ válido).
  - `refund_bank_name` é OBRIGATÓRIO.
  - `refund_branch_number` é OBRIGATÓRIO.
  - `refund_bank_account_number` é OBRIGATÓRIO.
  - `refund_bank_account_type` é OBRIGATÓRIO (`checking` ou `savings`).

### 1.5 Regras do Catálogo de Opções (`catalog_options` e `catalog_other_text`)
- Máximo de 1 opção por categoria (`institutional_tie`, `project_purpose`, `knowledge_area`, `funding_agency`).
- Se qualquer uma das opções selecionadas tiver código `other`, o campo `catalog_other_text` torna-se **OBRIGATÓRIO**.

---

## 2. Estratégia de Testes Massivos e Combinatórios

Crie/atualize a suíte em `apps/applications/tests/test_application_form.py` e adicione `test_massive_application_combinations.py` utilizando `@pytest.mark.parametrize` do `pytest` para cobrir as seguintes matrizes de teste:

### 2.1 Matriz de Teste da Modalidade e Validações Cruzadas
1. **Projeto Válido Completo:** Com coleta=True, orientador, declaração, autorização, todos os campos de 1 a 9 preenchidos e catálogo válido -> **DEVE PASSAR**.
2. **Projeto Inválido (Dados não coletados):** `modality='project'`, `data_already_collected=False` -> **DEVE FALHAR**.
3. **Projeto Inválido (Falta de campo do projeto):** `modality='project'`, omitindo `context_summary` ou qualquer item de 1 a 9 -> **DEVE FALHAR**.
4. **Projeto Inválido (Iniciação/Mestrado/Doutorado sem orientador/declaração):** Selecionar Doutorado sem `mentor_name` ou sem `mentor_declaration_accepted` -> **DEVE FALHAR**.
5. **Consulta Válida Completa:** `modality='consultation'`, sem exigir campos de projeto 1 a 9, sem exigir coleta=True -> **DEVE PASSAR**.
6. **Consulta sem Autorização de Dados:** `data_use_authorization_accepted=False` -> **DEVE FALHAR**.

### 2.2 Matriz de Dados Bancários / Reembolso
1. `wants_refund_receipt=True` com todos os dados bancários válidos -> **DEVE PASSAR**.
2. `wants_refund_receipt=True` omitindo cada um dos campos bancários individualmente (6 variações) -> **TODAS DEVEM FALHAR**.
3. `wants_refund_receipt=True` com CPF/CNPJ bancário inválido (`111.111.111-11`) -> **DEVE FALHAR**.
4. `wants_refund_receipt=False` com dados bancários vazios -> **DEVE PASSAR**.

### 2.3 Teste de Regressão com Amostragem Representativa
- Crie um teste de integração que simule a submissão de payloads contendo combinações representativas de inscrições para garantir compatibilidade com o histórico processado.