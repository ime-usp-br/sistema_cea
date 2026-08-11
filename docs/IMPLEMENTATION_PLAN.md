# Plano de Implementação: Inscrições CEA

## 🎯 Objetivo
Este documento serve como o roteiro principal (GPS) para a construção do sistema **Inscrições CEA**. 
Agentes de IA devem consultar este arquivo para entender o estado atual do projeto, marcar as tarefas concluídas com `[x]` e prosseguir de forma incremental.

## 📜 Regras de Operação para a IA
1. **Nunca pule fases:** A arquitetura é relacional. Uma fase depende da tabela/módulo da fase anterior.
2. **Ao iniciar uma tarefa:** Leia este arquivo para identificar o próximo `[ ]` pendente.
3. **Ao concluir uma tarefa:** Rode os testes (Pytest), linter (Ruff) e tipagem (MyPy). Se tudo passar, marque o item correspondente com `[x]` neste arquivo.
4. **Consulte a documentação:** Use o `docs/DATABASE_SCHEMA.md` para criar os Models e o `docs/ARCHITECTURE.md` para criar os Services.
5. **Testes:** Cada fase concluída deve implementar os testes descritos em `docs/TEST_SCENARIOS.md`.

---

## 🚀 Fases do Projeto

### Fase 1: Fundação e Setup (✅ Concluído via Starter Kit)
- [x] Configuração do Docker (Web, Postgres, Redis, Celery).
- [x] Configuração de Linters e Tipagem (Ruff, MyPy no `pyproject.toml`).
- [x] Módulo `accounts`: Custom User Model (`users.User`).
- [x] Autenticação Híbrida: Login local (HTML/Form) e rota base para Senha Única USP.

### Fase 2: Complemento de Identidade e Períodos Letivos
- [x] **App `users` (Complemento):** Adicionar campos `tax_id`, `codpes`, `is_email_verified`, `full_name` ao modelo `User`.
- [x] **App `users`:** Criar modelo `IdentityProviderLink` (para vínculo de Senha Única).
- [x] **App `terms`:** Criar o módulo de Períodos Letivos.
- [x] **App `terms`:** Criar o modelo `AcademicTerm` e expô-lo no Django Admin.
- [x] **Testes:** Validar `TS-AUTH-005` e criação de termos.

### Fase 3: Domínio Core (Inscrições e Catálogos)
- [x] **App `applications`:** Criar os modelos `CatalogOption` e `ApplicationCatalogSelection`.
- [x] **App `files`:** Criar o modelo genérico `FileAsset` (para metadados de arquivos no storage) e `ApplicationAttachment`.
- [x] **App `applications`:** Criar o modelo central `ServiceApplication` (com `soft_deleted_at`, relacionamentos, etc).
- [x] **Services:** Criar `ProtocolGenerator` para garantir protocolos únicos de 9 dígitos.
- [x] **Views/Forms:** Criar views e templates para o candidato enviar a inscrição (Projetos e Consultas).
- [x] **Testes:** Implementar suíte `TS-APP-001` até `TS-APP-010`.

### Fase 4: Auditoria de Dados (Fluxo Docente)
- [x] **App `audits`:** Criar os modelos `DatasetAuditSubmission`, `DatasetAuditReview` e `DatasetAuditResolution`.
- [x] **Services:** Implementar a máquina de estados no `DatasetAuditService` (aprovar, rejeitar, pedir correção).
- [x] **Views/Templates:** Telas para o candidato enviar o arquivo/link e para o docente/secretaria revisar.
- [x] **Testes:** Implementar suíte `TS-AUD-001` até `TS-AUD-017`.

### Fase 5: Finanças e Pagamentos (Core Financeiro)
- [ ] **App `payments`:** Criar os modelos `FeeRequirement` e `PaymentInstrument`.
- [ ] **App `payments`:** Criar `ManualPaymentConfirmation` e `RefundRequest`.
- [ ] **Services:** Criar `PaymentOrchestrationService` (garantindo a regra de Ouro: *apenas um instrumento ativo por taxa*).
- [ ] **Services:** Criar `ModalityChangeService` e `FeeCalculationService` (Lógica de crédito de R$ 60,00 na mudança de Consulta -> Projeto).
- [ ] **Testes:** Implementar suíte `TS-FEE-001` a `TS-FEE-008` e `TS-MAN-001`.

### Fase 6: Integração de Gateways (Pix e Boleto)
- [ ] **App `pix`:** Criar modelo `PixPaymentInstrument` e `PixWebhookEvent`.
- [ ] **App `pix`:** Implementar `PixGateway` (httpx) e `PixPaymentService`.
- [ ] **App `bank_slips`:** Criar modelo `BankSlipPaymentInstrument`.
- [ ] **App `bank_slips`:** Implementar `BankSlipGateway` (zeep SOAP) e `BankSlipPaymentService`.
- [ ] **Testes:** Implementar suítes `TS-PAY`, `TS-PIX` e `TS-BSL`.

### Fase 7: Agendamentos e Decisões
- [ ] **App `meetings`:** Criar modelos `ProjectScreening` (Triagem) e `ConsultationMeeting`.
- [ ] **Services:** Criar lógicas de agendamento, reagendamento, cancelamento e decisão final (Aprovado/Não Aprovado).
- [ ] **Views/Templates:** Interface da secretaria e docentes para gerenciar agenda e dar feedback.
- [ ] **Testes:** Implementar suíte `TS-MEET-001` até `TS-MEET-012`.

### Fase 8: Comunicação, Eventos e PDFs
- [ ] **App `notifications`:** Criar `NotificationTemplate` e `NotificationDispatch`.
- [ ] **Services:** Criar disparo assíncrono via Celery.
- [ ] **App `applications` (Eventos):** Criar `ApplicationEvent` para auditoria de histórico.
- [ ] **App `documents`:** Implementar geração de PDF da Ficha de Inscrição e Comprovantes usando HTML/WeasyPrint.
- [ ] **Testes:** Implementar `TS-NOT`, `TS-EVT` e `TS-NFR` (PDFs).

### Fase 9: Relatórios, Migração e Resgate (Legacy)
- [ ] **App `reports`:** Criar views e serviços para exportação CSV/XLSX do Relatório Financeiro e Auditoria.
- [ ] **App `imports`:** Criar modelo `LegacyOwnershipClaim` (Resgate de inscrições órfãs por token no e-mail).
- [ ] **Comandos:** Criar scripts (management commands) para importar os dados antigos de tabelas externas.
- [ ] **Testes:** Implementar `TS-REP`, `TS-CLAIM` e `TS-IMP`.

---

## 📈 Status Atual
**Progresso Geral:** A **Fase 4** foi concluída. O próximo passo é a **Fase 5** (Finanças e Pagamentos: Core Financeiro).