# ARCHITECTURE.md

## 1. Propósito

Este documento descreve a arquitetura do sistema **Inscrições CEA**, responsável por gerenciar o fluxo de inscrição, pagamento, auditoria de dados, agendamento, decisão, acompanhamento e cobrança dos serviços de assessoria estatística do **Centro de Estatística Aplicada (CEA) — IME/USP**.

O sistema é destinado a dois públicos:

1. **Candidatos**
   - acessam o sistema com login;
   - criam inscrições;
   - acompanham o andamento;
   - pagam taxas via Pix ou boleto;
   - enviam dados para auditoria em Projetos;
   - consultam anexos e histórico.

2. **Equipe interna**
   - administra períodos letivos;
   - analisa auditorias;
   - agenda triagens e reuniões;
   - gerencia cobranças;
   - confirma pagamentos manuais;
   - decide casos rejeitados;
   - emite relatórios;
   - preserva dados históricos para auditoria.

---

## 2. Princípios arquiteturais

### 2.1 Acesso autenticado

Toda interação com inscrições exige usuário autenticado.

Não existe formulário público de inscrição sem login.

O sistema possui:

- login com Senha Única USP;
- login com e-mail e senha para candidatos externos;
- recuperação de senha;
- vinculação de contas;
- resgate de inscrições existentes.

---

### 2.2 Inscrições pertencem a usuários

Cada inscrição possui um usuário responsável.

Inscrições criadas no portal possuem dono definido.

Inscrições importadas de dados existentes podem permanecer sem dono até que ocorra resgate seguro por parte do candidato.

---

### 2.3 Regras de negócio em serviços

Views e endpoints devem ser finos.

Regras críticas ficam em serviços dedicados:

- criação de inscrição;
- cálculo de taxas;
- geração de cobrança;
- escolha de método de pagamento;
- auditoria de dados;
- mudança de modalidade;
- transferência de período;
- reembolso administrativo;
- reconciliação de pagamentos.

---

### 2.4 Estados explícitos

O sistema usa códigos de estado estáveis para inscrições, auditorias, pagamentos e cobranças.

A interface exibe rótulos amigáveis em português, mas o banco e os serviços usam códigos internos.

---

### 2.5 Pagamentos como domínio próprio

Pix, boleto e pagamento manual fazem parte de um módulo financeiro próprio.

Esse módulo controla:

- taxas devidas;
- cobranças;
- instrumentos de pagamento;
- substituição de cobrança;
- expiração;
- confirmação;
- reembolso;
- conciliação.

---

### 2.6 Auditoria com histórico completo

Toda submissão de dados de Projeto é registrada.

Correções, aprovações, rejeições e decisões administrativas são preservadas.

---

### 2.7 Arquivos como ativos auditáveis

Todo arquivo relevante possui metadados:

- nome original;
- chave de armazenamento;
- tamanho;
- tipo MIME;
- checksum;
- data de upload;
- finalidade;
- inscrição relacionada.

---

### 2.8 Retenção integral

Registros e arquivos são mantidos por prazo indeterminado para fins de auditoria, histórico institucional e suporte administrativo.

Exclusões ou anonimizações somente ocorrem por decisão institucional explícita e registrada.

---

## 3. Stack recomendada

| Camada | Tecnologia |
|---|---|
| Linguagem | Python |
| Framework web | Django |
| Banco de dados | MySQL ou MariaDB |
| Templates | Django Templates |
| Frontend | HTML server-side + CSS + JavaScript progressivo |
| Autenticação USP | OAuth2/OpenID Connect com Senha Única |
| Autenticação externa | e-mail e senha |
| Fila/tarefas | Celery, Django-Q ou backend síncrono configurável |
| Pix | cliente HTTP/JSON com `httpx` |
| Boleto | cliente SOAP com `zeep` |
| PDF | HTML/CSS + WeasyPrint |
| Arquivos | storage local ou objeto storage privado |
| E-mail | SMTP |
| Relatórios | exportação CSV/XLSX |

---

## 4. Estrutura do projeto

```text
cea/
├── config/
│   ├── settings/
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
├── apps/
│   ├── accounts/
│   ├── terms/
│   ├── applications/
│   ├── payments/
│   ├── pix/
│   ├── bank_slips/
│   ├── audits/
│   ├── meetings/
│   ├── notifications/
│   ├── files/
│   ├── documents/
│   ├── reports/
│   ├── imports/
│   └── integrations/
├── templates/
├── static/
├── media/
└── manage.py
```

---

## 5. Módulos principais

### 5.1 `accounts`

Responsável por:

- usuários;
- login local;
- login via Senha Única;
- cadastro de candidatos;
- recuperação de senha;
- vinculação de identidade;
- papéis e permissões;
- resgate de inscrições existentes.

---

### 5.2 `terms`

Responsável por:

- períodos letivos;
- janelas de inscrição;
- período atual;
- próximo período;
- transferências automáticas.

---

### 5.3 `applications`

Responsável por:

- inscrições;
- protocolo;
- modalidade;
- estado principal;
- dados do candidato;
- dados do projeto;
- dados bancários para reembolso;
- anexos;
- vínculo com usuário dono.

---

### 5.4 `payments`

Responsável por:

- taxas devidas;
- estado financeiro agregado;
- orquestração de cobranças;
- pagamento manual;
- substituição de cobrança;
- solicitação de reembolso;
- relatório financeiro.

---

### 5.5 `pix`

Responsável por:

- geração de Pix;
- consulta;
- expiração;
- QR Code;
- webhook;
- reconciliação;
- histórico de eventos Pix.

---

### 5.6 `bank_slips`

Responsável por:

- geração de boleto registrado;
- consulta de situação;
- download de PDF;
- cancelamento;
- registro em caso de falha;
- operações em lote;
- substituição de boletos.

---

### 5.7 `audits`

Responsável por:

- envio de dados de Projeto;
- análise docente;
- pedido de correção;
- aprovação;
- rejeição;
- decisão administrativa;
- histórico de submissões.

---

### 5.8 `meetings`

Responsável por:

- triagens de Projeto;
- reuniões de Consulta;
- agendamento;
- reagendamento;
- cancelamento;
- decisão;
- feedback docente.

---

### 5.9 `notifications`

Responsável por:

- templates de e-mail;
- envio para candidato;
- envio para equipe interna;
- registro de despacho;
- controle de eventos notificados.

---

### 5.10 `files`

Responsável por:

- upload;
- validação de tamanho;
- armazenamento privado;
- download autorizado;
- checksum;
- importação de arquivos existentes.

---

### 5.11 `documents`

Responsável por:

- geração de PDFs;
- ficha completa;
- resumo da inscrição;
- comprovantes;
- relatórios em PDF, quando necessário.

---

### 5.12 `reports`

Responsável por:

- relatório financeiro;
- relatório de auditoria;
- exportações;
- sincronização de pagamentos.

---

### 5.13 `imports`

Responsável por:

- importação de dados existentes;
- preservação de inscrições históricas;
- importação de anexos;
- suporte ao resgate de contas;
- reconciliação pós-importação.

---

### 5.14 `integrations`

Responsável por:

- cliente Pix;
- cliente SOAP de boleto;
- integração com provedor de login USP;
- integração com storage externo, se aplicável;
- adaptadores para testes.

---

## 6. Nomenclatura de domínio

| Conceito | Nome técnico |
|---|---|
| Período letivo | `AcademicTerm` |
| Inscrição | `ServiceApplication` |
| Candidato | `User` com papel `candidate` |
| Taxa devida | `FeeRequirement` |
| Instrumento de pagamento | `PaymentInstrument` |
| Cobrança Pix | `PixPaymentInstrument` |
| Cobrança boleto | `BankSlipPaymentInstrument` |
| Pagamento manual | `ManualPaymentConfirmation` |
| Solicitação de reembolso | `RefundRequest` |
| Auditoria de dados | `DatasetAuditSubmission` |
| Revisão docente | `DatasetAuditReview` |
| Decisão administrativa | `DatasetAuditResolution` |
| Triagem de Projeto | `ProjectScreening` |
| Reunião de Consulta | `ConsultationMeeting` |
| Evento/auditoria | `ApplicationEvent` |
| Modelo de notificação | `NotificationTemplate` |
| Anexo de inscrição | `ApplicationAttachment` |
| Arquivo físico | `FileAsset` |
| Resgate de inscrição | `LegacyOwnershipClaim` |

---

## 7. Papéis e permissões

### 7.1 Papéis

| Papel | Descrição |
|---|---|
| `candidate` | candidato autenticado |
| `teacher` | docente que analisa auditorias e reuniões |
| `secretariat` | equipe administrativa e financeira |
| `administrator` | acesso total |

---

### 7.2 Candidato

Pode:

- criar conta;
- fazer login;
- criar inscrição;
- acompanhar inscrições próprias;
- escolher método de pagamento;
- gerar Pix;
- gerar boleto;
- enviar dados para auditoria;
- corrigir dados quando solicitado;
- baixar anexos próprios;
- ver histórico da inscrição.

Não pode:

- acessar inscrições de terceiros;
- alterar dados financeiros;
- confirmar pagamento;
- agendar reuniões;
- alterar modalidade;
- editar períodos;
- acessar relatórios internos.

---

### 7.3 Docente

Pode:

- visualizar inscrições relevantes;
- analisar dados enviados em auditoria;
- aprovar dados;
- rejeitar dados;
- solicitar correção;
- informar decisão em triagens e reuniões;
- registrar feedback.

Não deve acessar:

- dados financeiros completos;
- confirmação manual de pagamento;
- gestão de usuários;
- gestão de períodos;
- relatórios financeiros completos.

---

### 7.4 Secretaria

Pode:

- gerenciar inscrições;
- gerenciar períodos;
- confirmar pagamento manual;
- gerenciar cobranças;
- decidir auditorias rejeitadas;
- converter modalidade;
- transferir período;
- criar solicitações de reembolso;
- apoiar resgate de contas;
- acessar relatórios financeiros;
- gerenciar notificações.

---

### 7.5 Administrador

Pode:

- realizar tudo que a Secretaria pode;
- gerenciar usuários e papéis;
- acessar configurações sensíveis;
- executar operações administrativas avançadas;
- auditar o sistema.

---

## 8. Autenticação

## 8.1 Login obrigatório

A página inicial exige autenticação.

Ao acessar `/`:

- usuário autenticado é direcionado ao painel;
- usuário não autenticado vê login/cadastro.

Rotas principais:

```text
/entrar
/cadastro
/recuperar-senha
/auth/usp/login
/auth/usp/callback
```

---

## 8.2 Conta externa

Cadastro mínimo:

- nome completo;
- e-mail;
- senha;
- aceite de termos.

Campos opcionais:

- CPF/CNPJ;
- telefone;
- instituição.

Requisitos:

- senha com hash forte;
- confirmação de e-mail;
- recuperação de senha;
- rate limiting;
- proteção contra força bruta.

---

## 8.3 Login via Senha Única USP

Fluxo:

1. usuário escolhe entrar com Senha Única;
2. sistema redireciona ao provedor;
3. provedor autentica;
4. sistema recebe dados;
5. usuário local é criado ou atualizado;
6. sessão é iniciada.

Dados sincronizados:

- nome;
- e-mail;
- número USP.

---

## 8.4 Vinculação de identidades

Um usuário pode possuir mais de um método de login.

Entidade:

```text
IdentityProviderLink
```

Campos:

| Campo | Descrição |
|---|---|
| `user` | usuário local |
| `provider` | `local` ou `usp_senha_unica` |
| `external_id` | identificador externo |
| `external_email` | e-mail externo |
| `linked_at` | data de vinculação |

Regras:

- evitar duplicidade por e-mail;
- vinculação exige confirmação;
- eventos de segurança são registrados.

---

## 9. Períodos letivos

Entidade:

```text
AcademicTerm
```

Campos:

| Campo | Tipo | Descrição |
|---|---|---|
| `year` | inteiro | ano |
| `period` | choice | `first` ou `second` |
| `teaching_start_date` | date | início do período letivo |
| `teaching_end_date` | date | fim do período letivo |
| `submission_start_date` | date | início das inscrições |
| `submission_end_date` | date | fim das inscrições |
| `created_at` | datetime | criação |
| `updated_at` | datetime | atualização |

Rótulos:

```text
first = 1º Semestre
second = 2º Semestre
```

Regras:

- `year + period` único;
- período atual é o mais recente;
- próximo período:
  - `first` → `second` do mesmo ano;
  - `second` → `first` do ano seguinte;
- Projetos podem ser bloqueados fora da janela de inscrição;
- Consultas podem ser permitidas fora da janela, conforme regra institucional.

---

## 10. Inscrições

Entidade principal:

```text
ServiceApplication
```

---

## 10.1 Campos de identificação

| Campo | Descrição |
|---|---|
| `protocol` | protocolo único |
| `term` | período letivo |
| `owner` | usuário dono |
| `modality` | `project` ou `consultation` |
| `lifecycle_status` | status principal |
| `payment_state` | estado financeiro agregado |
| `dataset_audit_required` | se exige auditoria |
| `dataset_audit_state` | estado da auditoria |
| `origin` | `created_portal` ou `imported` |
| `modality_credit_amount` | crédito de modalidade |
| `soft_deleted_at` | exclusão lógica |

---

## 10.2 Dados de contato

| Campo | Descrição |
|---|---|
| `researcher_name` | nome do pesquisador |
| `contact_email` | e-mail de contato |
| `contact_phone` | telefone |
| `has_whatsapp` | telefone possui WhatsApp |
| `tax_id` | CPF/CNPJ do pesquisador |

---

## 10.3 Dados institucionais

| Campo | Descrição |
|---|---|
| `institution_name` | instituição/unidade |
| `course_name` | curso |
| `mentor_name` | orientador/colaborador |

Campos de múltipla escolha:

- vínculo institucional;
- finalidade do projeto;
- área de conhecimento;
- agência de fomento.

---

## 10.4 Reembolso

| Campo | Descrição |
|---|---|
| `wants_refund_receipt` | deseja recibo de reembolso |
| `refund_receipt_details` | dados para reembolso |

---

## 10.5 Conta bancária para reembolso

| Campo | Descrição |
|---|---|
| `refund_account_holder_name` | titular |
| `refund_account_holder_tax_id` | CPF/CNPJ do titular |
| `refund_bank_name` | banco |
| `refund_branch_number` | agência |
| `refund_bank_account_number` | conta |
| `refund_bank_account_type` | `checking` ou `savings` |

---

## 10.6 Dados do projeto

| Campo | Descrição |
|---|---|
| `project_title` | título |
| `context_summary` | aspectos gerais |
| `general_objectives` | objetivos gerais |
| `variables_and_measurements` | características e variáveis |
| `contextual_factors` | outras características relevantes |
| `sampling_and_limitations` | amostra, restrições e limitações |
| `data_management_plan` | armazenamento dos dados |
| `expected_results` | conclusões esperadas |
| `expected_support` | ajuda esperada do CEA |
| `data_already_collected` | dados já coletados |

---

## 10.7 Aceites

| Campo | Descrição |
|---|---|
| `data_use_authorization_accepted` | autorização de uso de dados |
| `mentor_declaration_accepted` | declaração de ciência do orientador |

---

## 10.8 Protocolo

Regras:

- protocolo único;
- 9 dígitos;
- preenchido com zeros à esquerda;
- gerado por serviço dedicado;
- colisão tratada com nova geração;
- índice único no banco.

Serviço:

```text
ProtocolGenerator
```

---

## 10.9 Origem da inscrição

Campo:

```text
origin
```

Valores:

| Valor | Descrição |
|---|---|
| `created_portal` | criada por usuário autenticado |
| `imported` | importada de dados existentes |

Para inscrições importadas:

```text
owner = NULL
origin = imported
legacy_contact_email = e-mail original
legacy_contact_tax_id = CPF/CNPJ original
```

---

## 11. Catálogo de opções

Entidades:

```text
CatalogOption
ApplicationCatalogSelection
```

---

## 11.1 `CatalogOption`

| Campo | Descrição |
|---|---|
| `category` | categoria |
| `code` | código estável |
| `label` | rótulo em português |
| `is_active` | ativo |

---

## 11.2 Categorias

| Categoria | Descrição |
|---|---|
| `institutional_tie` | vínculo institucional |
| `project_purpose` | finalidade do projeto |
| `knowledge_area` | área de conhecimento |
| `funding_agency` | agência de fomento |

---

## 11.3 Opções

### Vínculo institucional

| code | label |
|---|---|
| `student` | Estudante |
| `staff` | Funcionário |
| `faculty` | Professor |
| `other` | Outro |

### Finalidade

| code | label |
|---|---|
| `undergraduate_research` | Iniciação Científica |
| `master` | Mestrado |
| `doctorate` | Doutorado |
| `livre_docencia` | Livre Docência |
| `publication` | Publicação |
| `other` | Outra |

### Área de conhecimento

| code | label |
|---|---|
| `technological` | Tecnológica |
| `health_biological` | Médica ou Biológica |
| `social_human` | Social ou Humana |
| `economic` | Econômica |
| `other` | Outra |

### Agência de fomento

| code | label |
|---|---|
| `fapesp` | FAPESP |
| `finep` | FINEP |
| `cnpq` | CNPq |
| `other` | Outra |

Quando a opção for `other`, a inscrição armazena texto complementar.

---

## 12. Arquivos

Entidade central:

```text
FileAsset
```

Campos:

| Campo | Descrição |
|---|---|
| `id` | UUID |
| `original_filename` | nome original |
| `storage_key` | chave no storage |
| `content_type` | MIME type |
| `size_bytes` | tamanho |
| `sha256_checksum` | checksum |
| `purpose` | finalidade |
| `application` | inscrição relacionada |
| `uploaded_by` | usuário |
| `created_at` | data de criação |

Finalidades:

| `purpose` | Descrição |
|---|---|
| `application_attachment` | anexo da inscrição |
| `dataset_submission` | arquivo de auditoria |
| `payment_receipt` | comprovante |
| `pix_qrcode_image` | imagem QR |
| `pix_pdf` | PDF do Pix |
| `bank_slip_pdf` | PDF do boleto |
| `document_export` | documento gerado |

Regras:

- arquivos privados;
- download somente com permissão;
- validação de tamanho;
- validação de tipo;
- nomes sanitizados;
- checksum registrado.

---

## 13. Anexos de inscrição

Entidade:

```text
ApplicationAttachment
```

Campos:

| Campo | Descrição |
|---|---|
| `application` | inscrição |
| `file_asset` | arquivo |
| `description` | descrição opcional |
| `created_at` | data |

Regras:

- anexos de inscrição possuem limite total recomendado de 8 MB;
- múltiplos arquivos são permitidos;
- candidato vê anexos das próprias inscrições;
- equipe interna acessa conforme papel.

---

## 14. Fluxo do candidato

## 14.1 Projeto

```text
Login ou cadastro
  ↓
Nova inscrição Projeto
  ↓
Preenchimento do formulário
  ↓
Submissão
  ↓
Envio de dados para auditoria
  ↓
Análise docente
  ↓
Se aprovado:
    pagamento
  ↓
Agendamento de triagem
```

Se houver pedido de correção:

```text
Análise docente
  ↓
Pedido de correção
  ↓
Candidato corrige
  ↓
Nova análise
```

Se houver rejeição:

```text
Rejeição docente
  ↓
Decisão administrativa:
    - converter em consulta
    - rejeitar
    - transferir período
```

---

## 14.2 Consulta

```text
Login ou cadastro
  ↓
Nova inscrição Consulta
  ↓
Submissão
  ↓
Pagamento
  ↓
Agendamento de reunião de consulta
```

---

## 15. Máquina de estados da inscrição

## 15.1 Status principais

| Código | Rótulo sugerido |
|---|---|
| `awaiting_dataset_submission` | Aguardando envio de dados |
| `awaiting_dataset_review` | Aguardando análise de dados |
| `awaiting_dataset_correction` | Aguardando correção de dados |
| `dataset_rejected_pending_resolution` | Dados rejeitados — aguardando decisão |
| `awaiting_payment` | Aguardando pagamento |
| `awaiting_screening_scheduling` | Aguardando agendamento da triagem |
| `awaiting_screening_result` | Aguardando resultado da triagem |
| `awaiting_consultation_scheduling` | Aguardando agendamento da reunião de consulta |
| `awaiting_consultation_result` | Aguardando resultado da reunião de consulta |
| `approved_as_project` | Aprovado como projeto |
| `approved_as_consultation` | Aprovado como consulta |
| `not_approved` | Não aprovado |
| `transferred` | Transferida |
| `canceled` | Cancelada |

---

## 15.2 Fluxo de Projeto

```text
awaiting_dataset_submission
  ↓
awaiting_dataset_review
  ↓
Se correção solicitada:
    awaiting_dataset_correction
        ↓
    awaiting_dataset_review
  ↓
Se aprovado:
    awaiting_payment
        ↓
    awaiting_screening_scheduling
        ↓
    awaiting_screening_result
        ↓
    approved_as_project
    approved_as_consultation
    not_approved
```

Se rejeitado:

```text
awaiting_dataset_review
  ↓
dataset_rejected_pending_resolution
  ↓
convert_to_consultation
reject_application
transfer_term
```

---

## 15.3 Fluxo de Consulta

```text
submitted
  ↓
awaiting_payment
  ↓
awaiting_consultation_scheduling
  ↓
awaiting_consultation_result
  ↓
approved_as_project
approved_as_consultation
not_approved
```

---

## 16. Auditoria de dados

A auditoria é obrigatória para Projetos criados por usuários autenticados.

Ela ocorre antes do pagamento da taxa de inscrição.

---

## 16.1 Elegibilidade

Regras:

- somente Projetos podem passar por auditoria;
- somente inscrições com usuário dono podem ser obrigadas a passar pela auditoria;
- inscrições importadas sem dono não entram automaticamente na auditoria;
- após resgate da inscrição por conta autenticada, a secretaria pode habilitar auditoria caso a caso.

Campo:

```text
dataset_audit_required
```

---

## 16.2 Submissão de dados

Entidade:

```text
DatasetAuditSubmission
```

Campos:

| Campo | Descrição |
|---|---|
| `application` | inscrição |
| `submitted_by` | candidato |
| `submission_channel` | `file` ou `external_link` |
| `file_asset` | arquivo, se houver |
| `external_url` | URL externa, se houver |
| `external_link_declaration` | candidato declarou acesso |
| `note` | observação |
| `state` | estado |
| `submitted_at` | data |

---

## 16.3 Canal por arquivo

Regras:

- tamanho máximo: 10 MB;
- armazenado como `FileAsset`;
- propósito `dataset_submission`;
- download restrito;
- checksum registrado.

---

## 16.4 Canal por link externo

O sistema aceita qualquer URL externa válida.

Regras:

- candidato informa a URL;
- candidato declara que o link está acessível;
- o sistema não baixa automaticamente o conteúdo;
- docente analisa manualmente;
- se o link estiver inacessível, docente pode solicitar correção;
- a URL é exibida com atributos seguros:
  - `target="_blank"`
  - `rel="noopener noreferrer"`

Validações mínimas:

- URL bem formada;
- protocolo HTTP ou HTTPS;
- comprimento máximo razoável.

---

## 16.5 Revisão docente

Entidade:

```text
DatasetAuditReview
```

Campos:

| Campo | Descrição |
|---|---|
| `submission` | submissão |
| `reviewer` | docente |
| `outcome` | resultado |
| `note` | observação |
| `reviewed_at` | data |

Resultados possíveis:

| Código | Descrição |
|---|---|
| `approved` | aprovado |
| `rejected` | rejeitado |
| `needs_correction` | correção solicitada |

---

## 16.6 Pedido de correção

Quando o docente solicita correção:

1. submissão atual recebe estado `needs_correction`;
2. inscrição entra em `awaiting_dataset_correction`;
3. candidato é notificado;
4. candidato envia nova submissão;
5. nova submissão é criada;
6. inscrição volta para `awaiting_dataset_review`.

Histórico completo é preservado.

---

## 16.7 Decisão administrativa

Se o docente rejeitar os dados, a secretaria decide.

Entidade:

```text
DatasetAuditResolution
```

Campos:

| Campo | Descrição |
|---|---|
| `submission` | submissão rejeitada |
| `decided_by` | secretaria/admin |
| `resolution` | decisão |
| `note` | observação |
| `decided_at` | data |

Decisões possíveis:

| Código | Descrição |
|---|---|
| `convert_to_consultation` | converter em consulta |
| `reject_application` | rejeitar inscrição |
| `transfer_term` | transferir de período |

---

## 16.8 Efeitos das decisões

### Converter em consulta

Efeitos:

- modalidade vira `consultation`;
- inscrição segue fluxo de consulta;
- taxa de consulta é gerada se não houver pagamento aplicável;
- eventos registrados;
- candidato notificado.

### Rejeitar inscrição

Efeitos:

- status vira `not_approved`;
- inscrição encerrada;
- eventos registrados;
- candidato notificado.

Se houver pagamento anterior, a secretaria pode criar solicitação de reembolso ou avaliar conversão, conforme o caso.

### Transferir período

Efeitos:

- inscrição move para próximo período;
- mantém dados;
- mantém auditoria/submissões;
- se ainda aplicável, mantém necessidade de auditoria;
- evento registrado.

---

## 17. Pagamentos

O módulo financeiro usa entidades próprias.

Entidades principais:

```text
FeeRequirement
PaymentInstrument
PixPaymentInstrument
BankSlipPaymentInstrument
ManualPaymentConfirmation
RefundRequest
PaymentEvent
```

---

## 18. Taxas devidas

Entidade:

```text
FeeRequirement
```

Campos:

| Campo | Descrição |
|---|---|
| `application` | inscrição |
| `fee_type` | tipo de taxa |
| `base_amount` | valor base |
| `adjustment_amount` | ajuste |
| `amount` | valor final devido |
| `adjustment_reason` | motivo do ajuste |
| `reason` | motivo da taxa |
| `is_waived` | isenta |
| `waiver_reason` | motivo da isenção |
| `created_at` | criação |

Tipos de taxa:

| Código | Rótulo |
|---|---|
| `application_fee` | Taxa de inscrição |
| `project_fee` | Taxa de projeto |
| `supplement_fee` | Complemento de taxa |

Valores padrão:

| Situação | Valor |
|---|---:|
| Taxa de inscrição para Projeto | R$ 80,00 |
| Taxa de inscrição para Consulta | R$ 140,00 |
| Taxa de projeto | R$ 250,00 |
| Complemento padrão Projeto → Consulta | R$ 60,00 |

Os valores podem ser configuráveis, mas a taxa criada preserva o valor vigente no momento da criação.

---

## 19. Instrumentos de pagamento

Entidade base:

```text
PaymentInstrument
```

Campos comuns:

| Campo | Descrição |
|---|---|
| `fee_requirement` | taxa relacionada |
| `method` | `pix`, `bank_slip` ou `manual` |
| `state` | estado |
| `amount` | valor |
| `created_at` | criação |
| `expires_at` | expiração |
| `paid_at` | pagamento |
| `created_by` | usuário interno, se aplicável |
| `superseded_by` | instrumento substituto |

Estados:

| Estado | Descrição |
|---|---|
| `created` | criado |
| `active` | ativo |
| `paid` | pago |
| `expired` | expirado |
| `canceled` | cancelado |
| `superseded` | substituído |
| `failed` | falhou |
| `manual_confirmed` | confirmado manualmente |
| `requires_review` | requer revisão |

Regra fundamental:

```text
Apenas um instrumento ativo por taxa.
```

Serviço responsável:

```text
PaymentOrchestrationService
```

---

## 20. Escolha do método de pagamento

Na área logada, o candidato escolhe o método:

```text
Pagar com Pix
Pagar com boleto
```

Regras:

- Pix e boleto podem coexistir historicamente;
- apenas um instrumento ativo por vez;
- se o candidato escolher Pix:
  - boleto ativo não pago é marcado como substituído;
  - tenta-se cancelar o boleto no serviço externo se ainda possível;
- se o candidato escolher boleto:
  - Pix ativo é marcado como substituído ou expirado;
  - novo boleto é gerado;
- substituições preservam histórico.

---

## 21. Pix

O Pix é integrado via API REST/JSON.

Cliente:

```text
PixGateway
```

Implementação recomendada:

```text
httpx
```

---

## 21.1 Endpoints consumidos

| Operação | Endpoint |
|---|---|
| Gerar Pix | `POST /pix/gerar` |
| Consultar Pix | `GET /pix/<idfpix>` |
| Listar pagos | `GET /pix/listarConcluidos` |
| Gerar PDF | `GET /pix/<idfpix>/pdf` |
| Gerar QR Code | `GET /pix/<idfpix>/qrcode` |
| Simular pagamento | `PATCH /pix/<idfpix>/simularPag` |
| Configurar webhook | `POST /pix/webhookConfig` |
| Remover webhook | `DELETE /pix/webhookConfig` |

---

## 21.2 Entidade Pix

```text
PixPaymentInstrument
```

Campos específicos:

| Campo | Descrição |
|---|---|
| `payment_instrument` | relação com instrumento |
| `pix_reference` | `idfpix` |
| `qr_code_payload` | Pix copia e cola |
| `qr_code_image_asset` | imagem QR |
| `external_status` | status retornado |
| `generated_at` | geração |
| `expires_at` | expiração |
| `paid_at` | pagamento |
| `payer_name` | pagador |
| `payer_tax_id` | documento do pagador |
| `bank_return_code` | retorno bancário |

---

## 21.3 Expiração

O Pix expira em:

```text
1 hora
```

Equivalente a:

```text
3600 segundos
```

Esse valor é configurável, mas o padrão operacional é 1 hora.

Regras:

- após expiração, o instrumento vira `expired`;
- o candidato pode gerar novo Pix;
- a taxa continua pendente até pagamento válido;
- rotina periódica atualiza Pix expirados;
- reconciliação verifica pagamentos ocorridos próximos da expiração.

---

## 21.4 Geração do Pix

Serviço:

```text
PixPaymentService
```

Fluxo:

1. verificar taxa devida;
2. verificar se já existe Pix ativo;
3. se existir, reutilizar;
4. se expirado, substituir;
5. chamar `PixGateway.generate`;
6. salvar `idfpix`, QR Code e imagem;
7. registrar evento;
8. exibir para o candidato.

Payload mínimo:

```json
{
  "tipoPessoa": "PF",
  "docPesOrg": "12345678901",
  "nomePesOrg": "Nome da Pessoa",
  "valor": "80,00",
  "infoCobranca": "CEA 123456789 Taxa de inscrição",
  "expiracao": 3600,
  "codigoFonteRecurso": 423,
  "codigoUnidadeDespesa": 1,
  "estruturaHierarquica": "\\DISTRIBUIDOR"
}
```

Observações:

- `valor` em formato pt-BR;
- `docPesOrg` apenas números;
- `tipoPessoa` pode ser `PF` ou `PJ`;
- dados financeiros de produção devem vir de configuração.

---

## 21.5 Webhook Pix

Endpoint:

```text
POST /webhooks/pix
```

Header esperado:

```text
X-Token
```

Regras:

1. validar token;
2. registrar payload bruto;
3. buscar Pix pelo `idfpix`;
4. verificar valor;
5. ignorar eventos duplicados;
6. atualizar instrumento para pago;
7. atualizar taxa;
8. registrar evento;
9. atualizar painel do candidato.

Tabela de eventos:

```text
PixWebhookEvent
```

Campos:

| Campo | Descrição |
|---|---|
| `pix_reference` | `idfpix` |
| `raw_payload` | JSON bruto |
| `token_valid` | token válido |
| `processed` | processado |
| `error_message` | erro |
| `received_at` | recebimento |

---

## 21.6 Consulta ativa

Quando o candidato abre a página de pagamento:

- sistema consulta Pix;
- se necessário, usa parâmetro `verificar`;
- atualiza estado local;
- exibe status atual.

---

## 21.7 Reconciliação

Rotinas:

### Curto prazo

Consultar Pix ativos e expirados recentemente.

### Diário

Usar:

```text
listarConcluidos
```

Regra:

- período máximo de 30 dias;
- conciliar pagamentos não recebidos por webhook;
- registrar divergências.

Serviço:

```text
PixReconciliationService
```

---

## 22. Boleto bancário

O boleto é integrado via SOAP/WSDL.

Cliente:

```text
BankSlipGateway
```

Implementação recomendada:

```text
zeep
```

---

## 22.1 Endpoints/WSDL

Desenvolvimento:

```text
https://dev.uspdigital.usp.br/wsboleto/wsdl/boleto.wsdl
```

Produção:

```text
https://uspdigital.usp.br/wsboleto/wsdl/boleto.wsdl
```

---

## 22.2 Métodos consumidos

| Método | Uso |
|---|---|
| `gerarBoletoRegistrado` | gerar boleto |
| `obterSituacao` | consultar situação |
| `obterSituacaoLote` | consultar em lote |
| `obterBoleto` | baixar PDF |
| `cancelarBoleto` | cancelar boleto |
| `cancelarBoletoLote` | cancelar em lote |
| `registrarBoleto` | registrar em caso de falha |
| `obterDetalhe` | detalhar boleto |
| `obterDetalheLote` | detalhar em lote |

---

## 22.3 Entidade boleto

```text
BankSlipPaymentInstrument
```

Campos específicos:

| Campo | Descrição |
|---|---|
| `payment_instrument` | relação com instrumento |
| `bank_slip_reference` | código externo do boleto |
| `due_date` | vencimento |
| `bank_status` | status bancário |
| `document_amount` | valor do documento |
| `discount_amount` | desconto |
| `paid_amount` | valor pago |
| `registration_date` | data de registro |
| `payment_date` | data de pagamento |
| `cancellation_date` | data de cancelamento |
| `pdf_asset` | PDF armazenado, opcional |

Status bancário:

| Código | Descrição |
|---|---|
| `E` | Emitido |
| `P` | Pago |
| `V` | Verificar |
| `C` | Cancelado |

---

## 22.4 Autenticação SOAP

A autenticação é feita por headers SOAP:

```text
username
password
```

Regras:

- nomes sensíveis a maiúsculas/minúsculas;
- credenciais em variáveis de ambiente;
- não logar senha;
- timeouts configuráveis;
- tratamento de fault SOAP.

---

## 22.5 Geração de boleto

Serviço:

```text
BankSlipPaymentService
```

Fluxo:

1. verificar taxa devida;
2. verificar se já existe boleto ativo;
3. montar payload;
4. chamar `gerarBoletoRegistrado`;
5. armazenar `bank_slip_reference`;
6. registrar evento;
7. disponibilizar download.

Campos importantes:

| Campo | Observação |
|---|---|
| `codigoUnidadeDespesa` | código da unidade |
| `codigoFonteRecurso` | código da fonte |
| `estruturaHierarquica` | estrutura financeira |
| `valorDocumento` | formato `80.00` |
| `dataVencimentoBoleto` | formato `dd/mm/aaaa` |
| `tipoSacado` | `PF` ou `PJ` |
| `cpfCnpj` | apenas números |
| `nomeSacado` | nome do pagador |
| `instrucoesObjetoCobranca` | instruções |

Vencimento padrão:

```text
data de criação + 3 dias
```

Esse valor pode ser configurável.

---

## 22.6 Substituição de boleto

Quando uma cobrança é substituída:

1. boleto antigo vira `superseded`;
2. se ainda estiver emitido e não pago:
   - tentar cancelar no serviço externo;
3. novo boleto é criado;
4. histórico preservado.

---

## 23. Pagamento manual

Entidade:

```text
ManualPaymentConfirmation
```

Campos:

| Campo | Descrição |
|---|---|
| `payment_instrument` | instrumento |
| `confirmed_by` | usuário |
| `confirmed_at` | data |
| `note` | observação |

Regras:

- pagamento manual confirma taxa;
- não altera status externo do Pix/boleto;
- estado do instrumento pode ficar `manual_confirmed`;
- evento registrado;
- relatório financeiro considera manual como pago;
- nenhuma notificação automática é enviada ao candidato quando o pagamento é confirmado manualmente.

O candidato pode ver o status atualizado no painel.

---

## 24. Estado financeiro agregado

Serviço:

```text
FeeStatusService
```

Prioridade:

1. pago por Pix, boleto ou manual;
2. ativo e não expirado;
3. vencido;
4. expirado;
5. substituído;
6. não emitido.

Estados agregados sugeridos:

| Estado | Descrição |
|---|---|
| `paid` | pago |
| `active` | cobrança ativa |
| `overdue` | vencida |
| `expired` | expirada |
| `requires_review` | requer revisão |
| `pending` | pendente |
| `not_issued` | não emitido |

---

## 25. Regras financeiras

## 25.1 Projeto aprovado na auditoria

Quando um Projeto é aprovado na auditoria:

- gerar `application_fee` de R$ 80,00;
- candidato escolhe Pix ou boleto;
- após pagamento confirmado:
  - inscrição segue para `awaiting_screening_scheduling`.

---

## 25.2 Projeto aprovado como projeto

Quando a triagem ou decisão final aprova como Projeto:

- gerar `project_fee`;
- valor base: R$ 250,00;
- aplicar créditos de modalidade, se existirem.

---

## 25.3 Projeto aprovado como consulta

Quando um Projeto é aprovado como Consulta:

- se taxa de inscrição Projeto não paga:
  - gerar taxa de Consulta de R$ 140,00;
- se taxa de inscrição Projeto paga:
  - gerar complemento de R$ 60,00;
- se já existir complemento ativo:
  - não duplicar;
- se valor pago for igual ou superior a R$ 140,00:
  - nada a cobrar;
  - se houver excesso, encaminhar para análise/reembolso.

---

## 25.4 Consulta paga convertida em Projeto

Quando uma Consulta já paga se torna Projeto:

- o valor pago de R$ 140,00 é mantido;
- não há reembolso automático;
- registra-se crédito de modalidade de R$ 60,00;
- quando a inscrição for aprovada como Projeto:
  - taxa de projeto base: R$ 250,00;
  - desconto de R$ 60,00;
  - valor devido: R$ 190,00.

Exemplo:

```text
Taxa de consulta paga: R$ 140,00
Taxa de inscrição Projeto equivalente: R$ 80,00
Diferença: R$ 60,00

Taxa de projeto base: R$ 250,00
Crédito aplicado: R$ 60,00
Taxa de projeto devida: R$ 190,00
```

---

## 25.5 Consulta não paga convertida em Projeto

Quando uma Consulta ainda não paga se torna Projeto:

- cobrança de Consulta de R$ 140,00 é substituída;
- nenhuma cobrança de Projeto é gerada imediatamente antes da auditoria;
- após aprovação na auditoria:
  - gerar taxa de inscrição Projeto de R$ 80,00;
- não há crédito de modalidade, pois não houve pagamento anterior.

---

## 25.6 Projeto rejeitado sem pagamento

Como a auditoria ocorre antes do pagamento para Projetos novos:

- se o Projeto for rejeitado antes do pagamento:
  - nenhuma taxa é cobrada;
  - inscrição é encerrada ou transferida conforme decisão administrativa.

---

## 25.7 Projeto rejeitado com pagamento existente

Casos com pagamento existente podem ocorrer em:

- inscrições importadas;
- conversões de Consulta para Projeto;
- exceções administrativas.

Se uma inscrição paga for rejeitada:

- a secretaria pode criar solicitação de reembolso;
- ou pode converter em Consulta, se aplicável;
- a conversão recalcula taxas;
- se houver excesso de pagamento, pode-se criar solicitação de reembolso.

---

## 26. Solicitação de reembolso

Entidade:

```text
RefundRequest
```

Campos:

| Campo | Descrição |
|---|---|
| `application` | inscrição |
| `payment_instrument` | pagamento relacionado |
| `amount` | valor |
| `reason` | motivo |
| `status` | estado |
| `requested_by` | solicitante |
| `approved_by` | aprovador |
| `executed_at` | data de execução |
| `note` | observação |
| `created_at` | criação |

Estados:

| Estado | Descrição |
|---|---|
| `requested` | solicitada |
| `approved` | aprovada |
| `executed` | executada |
| `denied` | negada |

Regras:

- reembolso não é automático;
- execução ocorre fora do sistema;
- sistema registra solicitação, aprovação e execução;
- eventos são registrados.

---

## 27. Mudança de modalidade

Serviço:

```text
ModalityChangeService
```

Responsável por:

- validar permissão;
- validar estado atual;
- atualizar modalidade;
- atualizar status;
- recalcular taxas;
- registrar créditos;
- substituir cobranças ativas;
- gerar complementos;
- registrar eventos;
- notificar candidato quando aplicável.

---

## 27.1 Projeto → Consulta

Regra:

```text
Valor devido = Taxa de Consulta - valor já pago em taxa de inscrição
```

Casos:

| Situação | Ação |
|---|---|
| Projeto não pago | gerar taxa de Consulta de R$ 140,00 |
| Projeto pago R$ 80,00 | gerar complemento de R$ 60,00 |
| Complemento ativo existente | reutilizar |
| Pago R$ 140,00 ou mais | nada a cobrar; excesso vai para análise |

---

## 27.2 Consulta → Projeto

Regra:

| Situação | Ação |
|---|---|
| Consulta não paga | substituir cobrança por taxa de Projeto de R$ 80,00 após auditoria aprovada |
| Consulta paga R$ 140,00 | manter pagamento e registrar crédito de R$ 60,00 |
| Aprovado como Projeto | gerar taxa de projeto de R$ 190,00 se crédito de R$ 60,00 existir |

---

## 27.3 Auditoria após mudança para Projeto

Quando uma inscrição com usuário dono se torna Projeto:

- `dataset_audit_required` é habilitado;
- inscrição entra em `awaiting_dataset_submission`;
- exceções podem ser definidas pela secretaria.

Quando uma inscrição importada sem dono se torna Projeto:

- auditoria não é exigida automaticamente;
- secretaria pode habilitar após resgate da conta.

---

## 28. Transferência de período

Serviço:

```text
TermTransferService
```

Situações:

1. próximo período existe:
   - transferência imediata;
2. próximo período não existe:
   - marca transferência pendente;
3. próximo período criado:
   - transferências pendentes são processadas.

Campos na inscrição:

| Campo | Descrição |
|---|---|
| `transfer_pending` | aguardando transferência |
| `transfer_reason` | motivo |

Regras:

- transferência preserva histórico;
- transferência preserva pagamentos;
- transferência preserva auditoria, se existente;
- inscrição importada sem dono permanece sem dono após transferência;
- inscrição com dono mantém dono após transferência.

Eventos:

```text
term_transfer_requested
term_transfer_completed
term_transfer_pending
term_transfer_automatic
```

---

## 29. Triagens e reuniões

## 29.1 Triagem de Projeto

Entidade:

```text
ProjectScreening
```

Campos:

| Campo | Descrição |
|---|---|
| `application` | inscrição |
| `scheduled_date` | data |
| `scheduled_time` | hora |
| `meeting_mode` | `online` ou `in_person` |
| `virtual_link` | link |
| `place` | local |
| `decision` | decisão |
| `decision_note` | observação |
| `teacher_feedback` | feedback |
| `state` | estado |

Estados:

| Estado | Descrição |
|---|---|
| `scheduled` | agendada |
| `rescheduled` | reagendada |
| `canceled` | cancelada |
| `completed` | concluída |

---

## 29.2 Reunião de Consulta

Entidade:

```text
ConsultationMeeting
```

Campos equivalentes aos da triagem.

---

## 29.3 Decisões possíveis

| Código | Rótulo |
|---|---|
| `approved_as_project` | Aprovado como projeto |
| `approved_as_consultation` | Aprovado como consulta |
| `not_approved` | Não aprovado |

---

## 29.4 Feedback docente

Para triagem:

| Código | Rótulo |
|---|---|
| `screening_completed` | Triagem realizada |
| `screening_not_completed` | Triagem não realizada |

Para consulta:

| Código | Rótulo |
|---|---|
| `consultation_completed` | Consulta realizada |
| `consultation_not_completed` | Consulta não realizada |

Regra:

- feedback só pode ser registrado após data/hora do evento.

---

## 30. Notificações

Entidades:

```text
NotificationTemplate
NotificationDispatch
```

---

## 30.1 Templates

Campos:

| Campo | Descrição |
|---|---|
| `code` | código do evento |
| `name` | nome |
| `description` | descrição |
| `audience` | `candidate`, `center`, `teacher`, `secretariat` |
| `subject` | assunto |
| `body` | corpo |
| `is_active` | ativo |

---

## 30.2 Eventos recomendados

| Código | Descrição |
|---|---|
| `account_created` | conta criada |
| `email_verification` | confirmação de e-mail |
| `password_reset` | recuperação de senha |
| `application_submitted_candidate` | inscrição enviada para candidato |
| `application_submitted_center` | inscrição enviada para CEA |
| `payment_created` | cobrança criada |
| `payment_confirmed` | pagamento confirmado |
| `payment_expired` | cobrança expirada |
| `dataset_submitted` | dados enviados |
| `dataset_correction_requested` | correção solicitada |
| `dataset_approved` | dados aprovados |
| `dataset_rejected` | dados rejeitados |
| `dataset_resolution_completed` | decisão administrativa concluída |
| `screening_scheduled` | triagem agendada |
| `screening_rescheduled` | triagem reagendada |
| `screening_canceled` | triagem cancelada |
| `screening_decision` | decisão de triagem |
| `consultation_scheduled` | reunião agendada |
| `consultation_rescheduled` | reunião reagendada |
| `consultation_canceled` | reunião cancelada |
| `consultation_decision` | decisão de reunião |
| `term_transferred` | transferência de período |
| `legacy_claim_instructions` | instruções de resgate |

---

## 30.3 Regras de envio

- envio por fila;
- retry em falha;
- log de despacho;
- templates ativos por evento;
- variáveis renderizadas com Django Templates;
- não enviar dados sensíveis desnecessários.

---

## 30.4 Pagamento manual

Pagamento manual confirmado:

- atualiza status;
- registra evento;
- aparece no painel;
- não envia e-mail automático ao candidato.

---

## 31. Geração de PDF

A geração de PDF usa:

```text
HTML/CSS + WeasyPrint
```

Serviço:

```text
DocumentRenderingService
```

Documentos:

| Documento | Descrição |
|---|---|
| `application_summary_pdf` | resumo da inscrição |
| `application_full_pdf` | ficha completa |
| `payment_receipt_pdf` | comprovante |
| `dataset_audit_report_pdf` | relatório de auditoria |
| `screening_summary_pdf` | resumo de triagem |

Requisitos:

- suporte completo a UTF-8;
- campos livres com quebra de linha;
- paginação correta;
- cabeçalho e rodapé;
- escapamento automático via HTML;
- sem dependência de ferramentas frágeis de geração.

CSS essencial:

```css
.field-value {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
```

---

## 32. Relatórios

## 32.1 Relatório financeiro

Mostra:

- protocolo;
- modalidade;
- candidato;
- e-mail;
- tipo de taxa;
- método de pagamento;
- valor base;
- ajuste;
- valor final;
- estado;
- data de pagamento;
- pagamento manual;
- cobrança substituída;
- crédito de modalidade;
- solicitação de reembolso.

Ações:

- sincronizar Pix;
- sincronizar boletos;
- exportar CSV;
- exportar XLSX.

---

## 32.2 Relatório de auditoria

Mostra:

- protocolo;
- projeto;
- candidato;
- data de submissão;
- canal de envio;
- estado da análise;
- decisão docente;
- decisão administrativa;
- histórico de correções.

---

## 32.3 Exportações

Formatos:

- CSV com separador `;` e BOM UTF-8;
- XLSX;
- PDF, se necessário.

Serviço:

```text
ReportExportService
```

---

## 33. Eventos e auditoria

Entidade:

```text
ApplicationEvent
```

Campos:

| Campo | Descrição |
|---|---|
| `application` | inscrição |
| `event_code` | código |
| `description` | descrição |
| `actor` | usuário |
| `metadata` | dados adicionais |
| `occurred_at` | data/hora |

Eventos importantes:

- inscrição criada;
- reivindicação de inscrição;
- pagamento criado;
- pagamento confirmado;
- Pix expirado;
- boleto substituído;
- pagamento manual confirmado;
- dados enviados;
- correção solicitada;
- dados aprovados;
- dados rejeitados;
- decisão administrativa;
- mudança de modalidade;
- transferência de período;
- solicitação de reembolso;
- agendamento;
- reagendamento;
- cancelamento;
- decisão final.

---

## 34. Banco de dados

## 34.1 Convenções

| Item | Recomendação |
|---|---|
| Nomes | snake_case |
| Chaves primárias | `BIGINT` ou `UUID` |
| Chaves estrangeiras | `BIGINT` |
| Datas | `DATE` ou `DATETIME(6)` |
| Dinheiro | `DECIMAL(10,2)` |
| Booleanos | `TINYINT(1)` |
| Textos longos | `TEXT` ou `MEDIUMTEXT` |
| Charset | `utf8mb4` |
| Engine | InnoDB |

---

## 34.2 Tabelas principais

```text
users
identity_provider_links
academic_terms
service_applications
application_catalog_selections
catalog_options
file_assets
application_attachments
dataset_audit_submissions
dataset_audit_reviews
dataset_audit_resolutions
fee_requirements
payment_instruments
pix_payment_instruments
bank_slip_payment_instruments
manual_payment_confirmations
refund_requests
payment_events
pix_webhook_events
project_screenings
consultation_meetings
notification_templates
notification_dispatches
application_events
legacy_ownership_claims
```

---

## 34.3 Índices importantes

- `service_applications.protocol` único;
- `service_applications.owner`;
- `service_applications.term`;
- `service_applications.lifecycle_status`;
- `service_applications.modality`;
- `service_applications.dataset_audit_required`;
- `fee_requirements.application`;
- `payment_instruments.fee_requirement`;
- `payment_instruments.state`;
- `pix_payment_instruments.pix_reference` único;
- `bank_slip_payment_instruments.bank_slip_reference`;
- `application_events.application`;
- `application_events.occurred_at`;
- `dataset_audit_submissions.application`;
- `legacy_ownership_claims.application`.

---

## 35. Importação de dados existentes

A importação preserva dados históricos e permite auditoria.

---

## 35.1 Princípios

- preservar inscrições existentes;
- preservar anexos;
- preservar pagamentos;
- manter histórico visível internamente;
- permitir resgate seguro pelo candidato;
- não criar contas completas automaticamente sem validação.

---

## 35.2 Inscrições importadas

Ao importar:

```text
ServiceApplication.origin = imported
ServiceApplication.owner = NULL
ServiceApplication.lifecycle_status = mapeado
ServiceApplication.legacy_contact_email = e-mail original
ServiceApplication.legacy_contact_tax_id = documento original
```

Status existentes são mapeados para novos códigos.

---

## 35.3 Auditoria em inscrições importadas

Regra:

```text
Inscrições importadas sem dono não entram automaticamente em auditoria.
```

Motivo:

- auditoria depende de área logada;
- somente inscrições com usuário dono podem exigir envio de dados.

Após resgate:

- a secretaria pode habilitar auditoria caso a caso;
- se habilitada, a inscrição entra no fluxo de auditoria normal.

---

## 35.4 Transferência de inscrições importadas

Se uma inscrição importada precisar passar para o próximo período:

- transferência preserva origem importada;
- transferência preserva ausência de dono;
- transferência não habilita auditoria automaticamente;
- somente após resgate e decisão administrativa a auditoria pode ser exigida.

---

## 35.5 Usuários importados

Não criar senha automaticamente.

Estratégia:

1. importar dados de contato como referência;
2. manter inscrição sem dono;
3. permitir que usuário crie conta;
4. permitir resgate de inscrição;
5. validar por e-mail, protocolo ou documento;
6. vincular após confirmação.

---

## 35.6 Resgate de inscrição

Entidade:

```text
LegacyOwnershipClaim
```

Campos:

| Campo | Descrição |
|---|---|
| `user` | usuário logado |
| `application` | inscrição encontrada |
| `protocol` | protocolo informado |
| `contact_email` | e-mail informado |
| `contact_tax_id` | documento informado |
| `status` | estado |
| `verification_token_hash` | token |
| `verified_at` | confirmação |
| `reviewed_by` | revisão manual |
| `created_at` | criação |

Estados:

| Estado | Descrição |
|---|---|
| `pending` | pendente |
| `code_sent` | código enviado |
| `verified` | confirmada |
| `rejected` | rejeitada |
| `manually_approved` | aprovada manualmente |

Fluxo:

1. usuário logado acessa “Vincular inscrição existente”;
2. informa protocolo, e-mail ou documento;
3. sistema localiza candidato potencial;
4. envia código para e-mail registrado;
5. usuário confirma;
6. inscrição recebe `owner`.

Regras:

- nenhuma vinculação automática silenciosa;
- código expirável;
- rate limiting;
- log de tentativa;
- máscara de dados;
- aprovação manual para casos sensíveis.

---

## 35.7 Importação de anexos

Etapas:

1. inventariar arquivos existentes;
2. calcular checksum SHA-256;
3. associar arquivo à inscrição;
4. copiar para novo storage;
5. criar `FileAsset`;
6. criar `ApplicationAttachment`;
7. validar checksum após cópia;
8. gerar relatório de erros.

Metadados:

| Campo | Conteúdo |
|---|---|
| `original_filename` | nome original |
| `storage_key` | novo caminho |
| `legacy_path` | caminho antigo |
| `sha256_checksum` | checksum |
| `size_bytes` | tamanho |
| `content_type` | MIME |

---

## 35.8 Nova estrutura de storage

Sugestão:

```text
imported/applications/<application_id>/attachments/<uuid>/<sanitized_filename>
imported/applications/<application_id>/receipts/<uuid>/<sanitized_filename>
audits/applications/<application_id>/datasets/<uuid>/<sanitized_filename>
pix/<application_id>/<uuid>.png
bank_slips/<application_id>/<uuid>.pdf
```

Regras:

- não usar caminho original como identificador final;
- evitar nomes duplicados;
- usar UUID;
- preservar nome original no banco;
- storage privado.

---

## 35.9 Importação financeira

Para boletos existentes:

- pagos: importar como instrumentos pagos;
- cancelados: importar como cancelados;
- vencidos não pagos: importar como históricos;
- substituídos: importar como `superseded`;
- pagamentos manuais: importar como `manual_confirmed`.

Para cobranças novas:

- usar Pix ou boleto conforme escolha do candidato;
- evitar duplicidade;
- preservar histórico.

---

## 35.10 Retenção

Registros e arquivos importados são mantidos por prazo indeterminado.

Não há rotina automática de expurgo.

Acesso é controlado por permissões.

---

## 36. Fila e tarefas assíncronas

Tarefas recomendadas:

| Tarefa | Descrição |
|---|---|
| enviar notificações | e-mails |
| expirar Pix ativos | rotina periódica |
| consultar Pix ativos | verificação curta |
| reconciliar Pix | listar concluídos |
| sincronizar boletos | obter situação |
| sincronizar boletos em lote | relatório financeiro |
| processar resgates | e-mails e tokens |
| gerar relatórios pesados | exportações |
| importar arquivos | tarefa administrativa |

---

## 37. Configuração por ambiente

Variáveis recomendadas:

```text
DATABASE_URL
SECRET_KEY
ALLOWED_HOSTS
EMAIL_BACKEND
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
STORAGE_BACKEND
MEDIA_ROOT
QUEUE_BACKEND
```

Pix:

```text
PIX_BASE_URL
PIX_USERNAME
PIX_PASSWORD
PIX_WEBHOOK_TOKEN
PIX_FONTE_RECURSO
PIX_UNIDADE_DESPESA
PIX_ESTRUTURA_HIERARQUICA
PIX_EXPIRATION_SECONDS
```

Boleto:

```text
BANK_SLIP_WSDL_URL
BANK_SLIP_USERNAME
BANK_SLIP_PASSWORD
BANK_SLIP_TIMEOUT
```

Login USP:

```text
USP_OAUTH_CLIENT_ID
USP_OAUTH_CLIENT_SECRET
USP_OAUTH_REDIRECT_URI
USP_OAUTH_SCOPES
```

---

## 38. Segurança

## 38.1 Autenticação

- senhas com hash forte;
- recuperação de senha com token expirável;
- login social apenas com validação de e-mail;
- sessões seguras;
- logout explícito.

---

## 38.2 Autorização

- permissões verificadas no backend;
- candidato acessa apenas dados próprios;
- docente acessa apenas dados técnicos;
- secretaria acessa financeiro;
- admin acessa tudo.

---

## 38.3 Webhooks

- validar token;
- registrar payload;
- idempotência;
- alerta em divergência de valor;
- endpoint sem CSRF, mas com token.

---

## 38.4 Arquivos

- upload com limite de tamanho;
- validação de extensão;
- storage privado;
- download autorizado;
- checksum.

---

## 38.5 Links externos

- não baixar conteúdo automaticamente;
- validar formato da URL;
- exibir com `rel="noopener noreferrer"`;
- docente pode marcar link inacessível.

---

## 38.6 Dados pessoais

- minimizar exposição;
- CPF/CNPJ visíveis apenas quando necessário;
- logs sem dados sensíveis;
- trilha de auditoria;
- retenção integral com controle de acesso.

---

## 39. Observabilidade

Logs recomendados:

- falha de login;
- geração de Pix;
- pagamento confirmado;
- webhook inválido;
- falha SOAP;
- envio de e-mail;
- erro de importação;
- resgate de inscrição;
- geração de PDF;
- solicitação de reembolso.

Métricas úteis:

- inscrições por período;
- pagamentos por método;
- Pix expirados;
- webhook com falha;
- boletos vencidos;
- auditorias pendentes;
- tempo médio de análise;
- correções solicitadas;
- reembolsos solicitados.

Health checks:

- banco;
- storage;
- fila;
- e-mail;
- integração Pix;
- integração boleto.

---

## 40. Testes

## 40.1 Tipos

- unitários;
- integração;
- permissão;
- serviço;
- importação;
- fluxo completo;
- integrações externas com dublês.

---

## 40.2 Serviços com dublês

```text
PixGateway
BankSlipGateway
NotificationService
FileStorageService
DocumentRenderingService
OAuthProviderService
```

---

## 40.3 Cenários essenciais

### Autenticação

- cadastro externo;
- login USP;
- recuperação de senha;
- vínculo de identidade;
- bloqueio de acesso não autorizado.

### Inscrição

- criar Projeto;
- criar Consulta;
- protocolo único;
- validação de campos;
- anexos dentro do limite;
- anexos acima do limite.

### Auditoria

- enviar arquivo;
- enviar link externo;
- docente aprovar;
- docente solicitar correção;
- candidato corrigir;
- docente rejeitar;
- secretaria converter;
- secretaria rejeitar;
- secretaria transferir.

### Pix

- gerar Pix;
- expirar Pix em 1 hora;
- webhook válido;
- webhook inválido;
- webhook duplicado;
- reconciliação sem webhook;
- regeneração após expiração.

### Boleto

- gerar boleto;
- consultar situação;
- baixar PDF;
- cancelar boleto;
- substituir boleto;
- pagamento manual sem envio de e-mail.

### Pagamentos

- escolha Pix;
- escolha boleto;
- apenas uma cobrança ativa;
- substituição de cobrança;
- complemento Projeto → Consulta;
- crédito Consulta → Projeto;
- taxa de projeto com desconto de R$ 60,00.

### Importação

- importar inscrições;
- importar anexos;
- validar checksum;
- resgate por código enviado ao e-mail;
- vínculo manual;
- boletos pagos preservados;
- inscrição importada sem auditoria automática.

---

## 41. Telas principais

## 41.1 Candidato

| Tela | Descrição |
|---|---|
| Login | acesso |
| Cadastro | nova conta |
| Recuperar senha | redefinição |
| Painel | inscrições do usuário |
| Nova inscrição | formulário |
| Detalhe da inscrição | acompanhamento |
| Pagamento | Pix/boleto |
| Envio de dados | auditoria |
| Correção de dados | auditoria |
| Anexos | arquivos |
| Perfil | dados do usuário |
| Vincular inscrição existente | resgate |

---

## 41.2 Equipe interna

| Tela | Descrição |
|---|---|
| Períodos | gestão de termos |
| Inscrições | lista e detalhe |
| Auditoria de dados | fila de análise |
| Reuniões | triagens e consultas |
| Cobranças | pagamentos e vencimentos |
| Reembolsos | solicitações |
| Relatório financeiro | conciliação e exportação |
| Notificações | templates e envios |
| Usuários | papéis |
| Resgates | suporte a vínculo |

---

## 42. Rotas principais

```text
GET  /
GET  /entrar
POST /entrar
GET  /cadastro
POST /cadastro
GET  /recuperar-senha
POST /recuperar-senha
GET  /auth/usp/login
GET  /auth/usp/callback

GET  /painel
GET  /inscricoes/nova
POST /inscricoes/nova
GET  /inscricoes/<protocol>
GET  /inscricoes/<protocol>/pagamento
POST /inscricoes/<protocol>/pagamento/metodo
POST /inscricoes/<protocol>/pix/gerar
POST /inscricoes/<protocol>/pix/consultar
POST /inscricoes/<protocol>/boleto/gerar
GET  /inscricoes/<protocol>/dados
POST /inscricoes/<protocol>/dados/enviar
GET  /inscricoes/<protocol>/dados/corrigir
POST /inscricoes/<protocol>/dados/corrigir

POST /webhooks/pix

GET  /gestao/periodos
GET  /gestao/inscricoes
GET  /gestao/auditoria
GET  /gestao/reunioes
GET  /gestao/cobrancas
GET  /gestao/reembolsos
GET  /gestao/relatorios/financeiro
GET  /gestao/notificacoes
GET  /gestao/usuarios
GET  /gestao/resgates
```

---

## 43. Serviços de domínio

| Serviço | Responsabilidade |
|---|---|
| `ProtocolGenerator` | gerar protocolo único |
| `ApplicationSubmissionService` | criar inscrição |
| `LegacyClaimService` | vincular inscrição existente |
| `FeeCalculationService` | calcular taxas e créditos |
| `PaymentOrchestrationService` | orquestrar cobranças |
| `PixPaymentService` | gerar/consultar Pix |
| `PixReconciliationService` | reconciliar Pix |
| `BankSlipPaymentService` | gerir boletos |
| `ManualPaymentService` | confirmar pagamento manual |
| `RefundRequestService` | gerir reembolsos |
| `DatasetAuditService` | gerir auditoria |
| `ModalityChangeService` | mudar modalidade |
| `TermTransferService` | transferir período |
| `ProjectScreeningService` | gerir triagens |
| `ConsultationMeetingService` | gerir reuniões |
| `NotificationService` | enviar e-mails |
| `DocumentRenderingService` | gerar PDFs |
| `FileStorageService` | armazenar arquivos |
| `DataImportService` | importar dados |
| `AttachmentImportService` | importar anexos |

---

## 44. Integrações externas

## 44.1 Pix

- REST/JSON;
- cliente HTTP;
- autenticação por headers HTTP;
- webhook com token;
- expiração padrão de 1 hora;
- reconciliação periódica.

---

## 44.2 Boleto

- SOAP/WSDL;
- cliente especializado;
- autenticação por headers SOAP;
- operações em lote;
- PDF Base64;
- status `E`, `P`, `V`, `C`.

---

## 44.3 Login USP

- OAuth2/OpenID Connect;
- sincronização de usuário;
- vinculação de identidade.

---

## 44.4 E-mail

- SMTP;
- envio assíncrono;
- log de despacho.

---

## 44.5 Storage

- local ou objeto storage;
- privado;
- URLs assinadas ou download via aplicação.

---

## 45. Critérios de aceite arquitetural

A arquitetura é considerada aderente quando:

1. somente usuários autenticados acessarem inscrições;
2. candidatos acessarem apenas inscrições próprias;
3. novas inscrições gerarem protocolo único;
4. Projetos com usuário dono passarem por auditoria antes do pagamento;
5. docentes conseguirem aprovar, rejeitar ou solicitar correção;
6. secretaria conseguir decidir auditorias rejeitadas;
7. candidatos conseguirem escolher Pix ou boleto;
8. Pix expirar em 1 hora e permitir regeneração;
9. webhook Pix for seguro e idempotente;
10. boletos puderem ser gerados e consultados;
11. apenas uma cobrança ativa existir por taxa;
12. pagamentos manuais forem registrados sem envio de e-mail ao candidato;
13. conversões de modalidade recalcularem taxas corretamente;
14. Consulta paga convertida em Projeto gerar crédito de R$ 60,00;
15. taxa de projeto com crédito passar a R$ 190,00;
16. reembolsos forem controlados administrativamente;
17. anexos existentes forem preservados com checksum;
18. inscrições importadas permanecerem auditáveis;
19. resgate de inscrição exigir confirmação por código;
20. inscrições importadas sem dono não entrarem automaticamente em auditoria;
21. registros e arquivos forem mantidos por prazo indeterminado;
22. PDFs forem gerados de forma estável;
23. relatórios financeiros refletirem Pix, boleto, manual, créditos e reembolsos;
24. eventos permitirem auditoria completa;
25. integrações externas puderem ser simuladas em teste.
