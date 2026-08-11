# DATABASE_SCHEMA.md

## 1. Objetivo

Este documento descreve o esquema de banco de dados do sistema **Inscrições CEA**.

Ele cobre:

- usuários e identidades;
- períodos letivos;
- inscrições;
- auditoria de dados;
- pagamentos via Pix;
- pagamentos via boleto;
- pagamento manual;
- reembolsos;
- arquivos;
- eventos;
- notificações;
- resgate de inscrições importadas;
- relatórios e auditoria.

O esquema foi projetado para:

- preservar histórico;
- permitir auditoria;
- suportar pagamentos múltiplos;
- evitar perda de dados financeiros;
- permitir resgate seguro de inscrições importadas;
- manter anexos e documentos de forma rastreável;
- reter registros por prazo indeterminado.

---

## 2. Convenções gerais e Tradução para Django ORM

Apesar de o esquema estar documentado com comandos SQL para fins de clareza conceitual, regras rígidas e visualização, **a implementação física será feita inteiramente através do Django ORM**.

| Item | Convenção (Documentação / SQL) | Tradução Padrão (Django ORM) |
|---|---|---|
| SGBD | PostgreSQL | Base configurada no `settings.py` |
| Nomenclatura | `snake_case` com nomes exatos | Exige uso de `db_table = 'nome_da_tabela'` na classe `Meta` |
| Chaves primárias | `BIGSERIAL` ou `UUID` | `BigAutoField(primary_key=True)` ou `UUIDField` |
| Chaves estrangeiras | `BIGINT` ou `UUID` | `models.ForeignKey(..., on_delete=...)` |
| Datas simples | `DATE` | `models.DateField()` |
| Data/hora com fuso | `TIMESTAMP WITH TIME ZONE` | `models.DateTimeField()` |
| Dinheiro | `DECIMAL(10,2)` | `models.DecimalField(max_digits=10, decimal_places=2)` |
| Booleanos | `BOOLEAN` | `models.BooleanField()` |
| Textos longos | `TEXT` | `models.TextField()` |
| Metadados estruturados| `JSONB` | `models.JSONField()` |
| Timestamp criação | `DEFAULT CURRENT_TIMESTAMP` | `auto_now_add=True` |
| Timestamp atualização| Manipulado pelo framework | `auto_now=True` |
| Exclusão lógica | `soft_deleted_at` | `models.DateTimeField(null=True, blank=True)` |
| Retenção | por prazo indeterminado | Não há purga automática |

> **Nota para Agentes de IA:** NUNCA crie tabelas via *raw SQL*. Use exclusivamente Models do Django e migrações padrão. SEMPRE mapeie o nome exato da tabela em `class Meta: db_table = 'nome_exato'`.

---

## 3. Diagrama textual

```text
users
  ├── identity_provider_links
  ├── service_applications
  ├── dataset_audit_submissions
  ├── dataset_audit_reviews
  ├── dataset_audit_resolutions
  ├── manual_payment_confirmations
  ├── refund_requests
  ├── application_events
  └── legacy_ownership_claims

academic_terms
  └── service_applications

service_applications
  ├── application_catalog_selections
  ├── application_attachments
  ├── dataset_audit_submissions
  ├── fee_requirements
  ├── project_screenings
  ├── consultation_meetings
  ├── application_events
  ├── notification_dispatches
  ├── refund_requests
  └── legacy_ownership_claims

catalog_options
  └── application_catalog_selections

file_assets
  ├── application_attachments
  ├── dataset_audit_submissions
  ├── pix_payment_instruments
  └── bank_slip_payment_instruments

fee_requirements
  └── payment_instruments
        ├── pix_payment_instruments
        ├── bank_slip_payment_instruments
        └── manual_payment_confirmations
```

---

## 4. Tabelas principais

### 4.1 `users`

Representa usuários autenticados. O sistema usa um Custom User Model do Django estendendo `AbstractUser`.

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    password VARCHAR(128) NULL,
    last_login TIMESTAMP WITH TIME ZONE NULL,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    tax_id VARCHAR(20) NULL,
    codpes INT NULL,
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified_at TIMESTAMP WITH TIME ZONE NULL,
    is_staff BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    date_joined TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT uq_users_tax_id UNIQUE (tax_id),
    CONSTRAINT uq_users_codpes UNIQUE (codpes)
);
```

### 4.2 `identity_provider_links`

Vincula métodos de autenticação ao usuário (Login Híbrido).

```sql
CREATE TABLE identity_provider_links (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    provider VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    external_email VARCHAR(255) NULL,
    linked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_identity_provider_links_external UNIQUE (provider, external_id),
    CONSTRAINT uq_identity_provider_links_user_provider UNIQUE (user_id, provider),

    CONSTRAINT fk_identity_provider_links_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

Valores para `provider`:
```text
local
usp_senha_unica
```

---

### 4.3 `academic_terms`

Representa períodos letivos.

```sql
CREATE TABLE academic_terms (
    id BIGSERIAL PRIMARY KEY,
    year SMALLINT NOT NULL,
    period VARCHAR(10) NOT NULL,
    teaching_start_date DATE NULL,
    teaching_end_date DATE NULL,
    submission_start_date DATE NULL,
    submission_end_date DATE NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_academic_terms_year_period UNIQUE (year, period),
    CONSTRAINT chk_academic_terms_period CHECK (period IN ('first', 'second'))
);
```

---

### 4.4 `service_applications`

Tabela central de inscrições.

```sql
CREATE TABLE service_applications (
    id BIGSERIAL PRIMARY KEY,

    term_id BIGINT NOT NULL,
    owner_id BIGINT NULL,

    protocol CHAR(9) NOT NULL,
    modality VARCHAR(20) NOT NULL,
    lifecycle_status VARCHAR(60) NOT NULL DEFAULT 'submitted',
    payment_state VARCHAR(30) NULL,

    dataset_audit_required BOOLEAN NOT NULL DEFAULT FALSE,
    dataset_audit_state VARCHAR(40) NULL,

    origin VARCHAR(20) NOT NULL DEFAULT 'created_portal',
    modality_credit_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,

    transfer_pending BOOLEAN NOT NULL DEFAULT FALSE,
    transfer_reason TEXT NULL,

    researcher_name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50) NULL,
    has_whatsapp BOOLEAN NOT NULL DEFAULT FALSE,
    tax_id VARCHAR(20) NULL,

    institution_name VARCHAR(255) NULL,
    course_name VARCHAR(255) NULL,
    mentor_name VARCHAR(255) NULL,

    wants_refund_receipt BOOLEAN NOT NULL DEFAULT FALSE,
    refund_receipt_details TEXT NULL,

    refund_account_holder_name VARCHAR(255) NULL,
    refund_account_holder_tax_id VARCHAR(20) NULL,
    refund_bank_name VARCHAR(255) NULL,
    refund_branch_number VARCHAR(50) NULL,
    refund_bank_account_number VARCHAR(50) NULL,
    refund_bank_account_type VARCHAR(20) NULL,

    project_title TEXT NULL,
    context_summary TEXT NULL,
    general_objectives TEXT NULL,
    variables_and_measurements TEXT NULL,
    contextual_factors TEXT NULL,
    sampling_and_limitations TEXT NULL,
    data_management_plan TEXT NULL,
    expected_results TEXT NULL,
    expected_support TEXT NULL,
    data_already_collected BOOLEAN NULL,

    data_use_authorization_accepted BOOLEAN NULL,
    mentor_declaration_accepted BOOLEAN NULL,

    legacy_contact_email VARCHAR(255) NULL,
    legacy_contact_tax_id VARCHAR(20) NULL,

    soft_deleted_at TIMESTAMP WITH TIME ZONE NULL,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_service_applications_protocol UNIQUE (protocol),
    CONSTRAINT fk_service_applications_term FOREIGN KEY (term_id) REFERENCES academic_terms(id) ON DELETE RESTRICT,
    CONSTRAINT fk_service_applications_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_service_applications_modality CHECK (modality IN ('project', 'consultation')),
    CONSTRAINT chk_service_applications_origin CHECK (origin IN ('created_portal', 'imported')),
    CONSTRAINT chk_service_applications_modality_credit CHECK (modality_credit_amount >= 0)
);

CREATE INDEX idx_service_applications_term ON service_applications(term_id);
CREATE INDEX idx_service_applications_owner ON service_applications(owner_id);
CREATE INDEX idx_service_applications_protocol ON service_applications(protocol);
```

---

### 4.5 `catalog_options`

Opções de catálogo para campos de múltipla escolha.

```sql
CREATE TABLE catalog_options (
    id SMALLSERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    label VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_catalog_options_category_code UNIQUE (category, code),
    CONSTRAINT chk_catalog_options_category CHECK (
        category IN ('institutional_tie', 'project_purpose', 'knowledge_area', 'funding_agency')
    )
);
```

---

### 4.6 `application_catalog_selections`

Relaciona inscrições com opções de catálogo.

```sql
CREATE TABLE application_catalog_selections (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL,
    option_id SMALLINT NOT NULL,
    other_text VARCHAR(255) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_application_catalog_selections UNIQUE (application_id, option_id),
    CONSTRAINT fk_app_catalog_selections_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE CASCADE,
    CONSTRAINT fk_app_catalog_selections_opt FOREIGN KEY (option_id) REFERENCES catalog_options(id) ON DELETE RESTRICT
);
```

---

### 4.7 `file_assets`

Metadados centrais de arquivos, referenciando caminhos no Storage/S3.

```sql
CREATE TABLE file_assets (
    id UUID PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    storage_key VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NULL,
    size_bytes BIGINT NULL,
    sha256_checksum CHAR(64) NULL,
    purpose VARCHAR(50) NOT NULL,
    application_id BIGINT NULL,
    uploaded_by BIGINT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_file_assets_storage_key UNIQUE (storage_key),
    CONSTRAINT fk_file_assets_application FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE SET NULL,
    CONSTRAINT fk_file_assets_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_file_assets_size CHECK (size_bytes IS NULL OR size_bytes >= 0)
);
```

---

### 4.8 `application_attachments`

Anexos manuais de inscrição.

```sql
CREATE TABLE application_attachments (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL,
    file_asset_id UUID NOT NULL,
    description VARCHAR(255) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_application_attachments_file UNIQUE (file_asset_id),
    CONSTRAINT fk_app_attachments_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE CASCADE,
    CONSTRAINT fk_app_attachments_file FOREIGN KEY (file_asset_id) REFERENCES file_assets(id) ON DELETE CASCADE
);
```

---

### 4.9 `dataset_audit_submissions`

Submissões de dados para auditoria (Fluxo do Docente).

```sql
CREATE TABLE dataset_audit_submissions (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL,
    submitted_by BIGINT NULL,
    submission_channel VARCHAR(20) NOT NULL,
    file_asset_id UUID NULL,
    external_url VARCHAR(2048) NULL,
    external_link_declaration BOOLEAN NOT NULL DEFAULT FALSE,
    note TEXT NULL,
    state VARCHAR(30) NOT NULL DEFAULT 'submitted',
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT fk_audit_submissions_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_submissions_user FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_submissions_file FOREIGN KEY (file_asset_id) REFERENCES file_assets(id) ON DELETE RESTRICT,
    CONSTRAINT chk_audit_submissions_channel CHECK (submission_channel IN ('file', 'external_link'))
);
```

---

### 4.10 `dataset_audit_reviews` e `dataset_audit_resolutions`

```sql
CREATE TABLE dataset_audit_reviews (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL,
    reviewer_id BIGINT NULL,
    outcome VARCHAR(20) NOT NULL,
    note TEXT NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_dataset_audit_reviews_submission UNIQUE (submission_id),
    CONSTRAINT fk_audit_reviews_submission FOREIGN KEY (submission_id) REFERENCES dataset_audit_submissions(id) ON DELETE CASCADE,
    CONSTRAINT fk_audit_reviews_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE dataset_audit_resolutions (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL,
    application_id BIGINT NOT NULL,
    target_term_id BIGINT NULL,
    decided_by BIGINT NULL,
    resolution VARCHAR(30) NOT NULL,
    note TEXT NULL,
    decided_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_dataset_audit_resolutions_submission UNIQUE (submission_id),
    CONSTRAINT fk_audit_resolutions_submission FOREIGN KEY (submission_id) REFERENCES dataset_audit_submissions(id) ON DELETE CASCADE,
    CONSTRAINT fk_audit_resolutions_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE RESTRICT
);
```

---

### 4.11 `fee_requirements`

Tabela abstrata das "Taxas devidas" que devem ser pagas (Base para o sistema financeiro).

```sql
CREATE TABLE fee_requirements (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL,
    fee_type VARCHAR(30) NOT NULL,
    base_amount DECIMAL(10,2) NOT NULL,
    adjustment_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    amount DECIMAL(10,2) NOT NULL,
    adjustment_reason VARCHAR(255) NULL,
    reason VARCHAR(255) NOT NULL,
    is_waived BOOLEAN NOT NULL DEFAULT FALSE,
    waiver_reason VARCHAR(255) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT fk_fee_requirements_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE RESTRICT
);
```

---

### 4.12 Módulo Financeiro: `payment_instruments`

Registra as tentativas/instâncias de pagamento atreladas a uma `fee_requirement`.

```sql
CREATE TABLE payment_instruments (
    id BIGSERIAL PRIMARY KEY,
    fee_requirement_id BIGINT NOT NULL,
    method VARCHAR(20) NOT NULL,
    state VARCHAR(30) NOT NULL DEFAULT 'created',
    amount DECIMAL(10,2) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NULL,
    paid_at TIMESTAMP WITH TIME ZONE NULL,
    created_by BIGINT NULL,
    superseded_by BIGINT NULL,
    active_unique_fee_token BIGINT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_payment_instruments_active UNIQUE (active_unique_fee_token),
    CONSTRAINT fk_payment_instruments_fee FOREIGN KEY (fee_requirement_id) REFERENCES fee_requirements(id) ON DELETE RESTRICT,
    CONSTRAINT chk_payment_instruments_method CHECK (method IN ('pix', 'bank_slip', 'manual'))
);
```

#### Detalhes Específicos (Pix e Boleto)
```sql
CREATE TABLE pix_payment_instruments (
    id BIGSERIAL PRIMARY KEY,
    payment_instrument_id BIGINT NOT NULL,
    pix_reference VARCHAR(35) NOT NULL,
    qr_code_payload VARCHAR(255) NOT NULL,
    qr_code_image_asset_id UUID NULL,
    external_status VARCHAR(20) NULL,
    generated_at TIMESTAMP WITH TIME ZONE NULL,
    expires_at TIMESTAMP WITH TIME ZONE NULL,
    paid_at TIMESTAMP WITH TIME ZONE NULL,
    payer_name VARCHAR(150) NULL,
    payer_tax_id VARCHAR(14) NULL,
    bank_return_code VARCHAR(35) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_pix_payment_instruments_payment UNIQUE (payment_instrument_id),
    CONSTRAINT uq_pix_payment_instruments_ref UNIQUE (pix_reference),
    CONSTRAINT fk_pix_instruments_payment FOREIGN KEY (payment_instrument_id) REFERENCES payment_instruments(id) ON DELETE CASCADE
);

CREATE TABLE bank_slip_payment_instruments (
    id BIGSERIAL PRIMARY KEY,
    payment_instrument_id BIGINT NOT NULL,
    bank_slip_reference VARCHAR(60) NOT NULL,
    due_date DATE NULL,
    bank_status CHAR(1) NULL,
    document_amount DECIMAL(10,2) NULL,
    discount_amount DECIMAL(10,2) NULL,
    paid_amount DECIMAL(10,2) NULL,
    registration_date DATE NULL,
    payment_date DATE NULL,
    cancellation_date DATE NULL,
    pdf_asset_id UUID NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_bank_slip_payment_instruments_payment UNIQUE (payment_instrument_id),
    CONSTRAINT uq_bank_slip_payment_instruments_ref UNIQUE (bank_slip_reference),
    CONSTRAINT fk_bank_slip_instruments_payment FOREIGN KEY (payment_instrument_id) REFERENCES payment_instruments(id) ON DELETE CASCADE
);

CREATE TABLE manual_payment_confirmations (
    id BIGSERIAL PRIMARY KEY,
    payment_instrument_id BIGINT NOT NULL,
    confirmed_by BIGINT NULL,
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    note TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_manual_payment_confirmations_payment UNIQUE (payment_instrument_id),
    CONSTRAINT fk_manual_payment_confirmations_payment FOREIGN KEY (payment_instrument_id) REFERENCES payment_instruments(id) ON DELETE CASCADE
);
```

---

### 4.13 Eventos e Webhooks

```sql
CREATE TABLE pix_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    pix_reference VARCHAR(35) NOT NULL,
    raw_payload JSONB NOT NULL,
    token_valid BOOLEAN NOT NULL DEFAULT FALSE,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payment_events (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NULL,
    fee_requirement_id BIGINT NULL,
    payment_instrument_id BIGINT NULL,
    event_code VARCHAR(100) NOT NULL,
    description TEXT NULL,
    metadata JSONB NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE application_events (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL,
    event_code VARCHAR(100) NOT NULL,
    description TEXT NULL,
    actor_id BIGINT NULL,
    metadata JSONB NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

### 4.14 Módulo de Agendamentos (Triagens e Reuniões)

```sql
CREATE TABLE project_screenings (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL,
    scheduled_date DATE NOT NULL,
    scheduled_time TIME NOT NULL,
    meeting_mode VARCHAR(20) NOT NULL,
    virtual_link VARCHAR(2048) NULL,
    place VARCHAR(255) NULL,
    decision VARCHAR(40) NULL,
    decision_note TEXT NULL,
    teacher_feedback VARCHAR(50) NULL,
    state VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_project_screenings_application UNIQUE (application_id),
    CONSTRAINT fk_project_screenings_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE RESTRICT
);

CREATE TABLE consultation_meetings (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL,
    scheduled_date DATE NOT NULL,
    scheduled_time TIME NOT NULL,
    meeting_mode VARCHAR(20) NOT NULL,
    virtual_link VARCHAR(2048) NULL,
    place VARCHAR(255) NULL,
    decision VARCHAR(40) NULL,
    decision_note TEXT NULL,
    teacher_feedback VARCHAR(50) NULL,
    state VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_consultation_meetings_application UNIQUE (application_id),
    CONSTRAINT fk_consultation_meetings_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE RESTRICT
);
```

---

### 4.15 Comunicação e Legado

```sql
CREATE TABLE notification_templates (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(255) NULL,
    audience VARCHAR(30) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT uq_notification_templates_code UNIQUE (code)
);

CREATE TABLE legacy_ownership_claims (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NULL,
    application_id BIGINT NULL,
    protocol CHAR(9) NULL,
    contact_email VARCHAR(255) NULL,
    contact_tax_id VARCHAR(20) NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    verification_token_hash VARCHAR(255) NULL,
    code_expires_at TIMESTAMP WITH TIME ZONE NULL,
    verified_at TIMESTAMP WITH TIME ZONE NULL,
    reviewed_by BIGINT NULL,
    review_note TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    CONSTRAINT fk_legacy_ownership_claims_app FOREIGN KEY (application_id) REFERENCES service_applications(id) ON DELETE SET NULL
);
```

---

## 5. Notas Finais sobre a Orquestração ORM

Reitera-se que o Django é a fonte da verdade na aplicação. O Agente e o Desenvolvedor devem focar em usar os utilitários de ORM do Python:

- Use `JSONField` nativo do Django para representar JSONB do Postgres.
- A consistência e equação de taxas (ex: `amount = base_amount + adjustment_amount`) deve ser garantida dentro da classe do Serviço em Python (ex: `FeeCalculationService`), ou sobrescrevendo o método `save()` do Model.
- Exclusões de Inscrições devem atualizar o campo `soft_deleted_at` com `timezone.now()`, nunca chamando um drop físico da linha.
