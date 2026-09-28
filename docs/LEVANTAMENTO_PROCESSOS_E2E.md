# Levantamento de Processos — Legado (Laravel) × Novo (Django) — base para testes E2E

**Objetivo:** mapear todos os **processos/jornadas** (etapas pelas quais os usuários passam) para
servir de base à criação dos testes E2E de navegador (happy paths e problemas óbvios).
O foco é **fluxo de ponta a ponta**, diferente do `docs/LEVANTAMENTO_LEGADO_VS_NOVO.md`, que é
focado em **apresentação de tela** (colunas/rótulos/menu).

> **Regra de verdade:** exceto as **novas funcionalidades** (login antes de submeter, submissão e
> auditoria de dados, emissão/acompanhamento de Pix e boleto, reembolso, resgate de inscrição), o
> **sistema legado é a fonte de verdade**. Este documento confronta a documentação existente com o
> código real do legado e do sistema novo.

---

## 1. Resposta curta: existe documentação de processos?

**Existe documentação, mas nenhuma consolidada de "processos passo a passo para E2E".**

| Documento | O que cobre | Confiabilidade |
|---|---|---|
| `docs/ARCHITECTURE.md` | Fluxos e máquina de estados do **sistema novo** (spec) | Boa como spec, mas **não descreve o legado** e diverge do código em pontos (ver §7) |
| `docs/TEST_SCENARIOS.md` | Cenários de teste do **sistema novo**, por módulo (não por jornada) | Parcial: vários cenários não batem com o código implementado (§7.1) |
| `docs/LEVANTAMENTO_LEGADO_VS_NOVO.md` | Comparação de **telas/colunas/rótulos** (Secretaria) | Correta no escopo, porém **desatualizada** em 2 itens P0 (§7.3) |
| `inscricoes-cea/docs/ANALISE_REESCRITA_DJANGO.md` | Análise profunda do **legado** (features, views, schema, regras) | **Alta** — melhor fonte documental sobre o legado |
| `inscricoes-cea/docs/PROJECT_FEATURES.md` | Visão geral do legado | Média; desatualizada (cita Pix, que não existe no legado) |
| `inscricoes-cea/docs/TEST_PLAN.md` | 7 casos E2E/manuais do legado | **Baixa** — rota e valores incorretos; não é fonte de verdade |

**Conclusão:** faltava o mapeamento de **jornadas**. É o que este documento entrega.

---

## 2. Fontes, método e acesso

- **Legado (fonte de verdade):** `/home/ayrtondouglas/ime/dev/inscricoes-cea` (Laravel 8), container
  `inscricoes-cea-app` (compose `inscricoes-cea`) e site `http://inscricao.cea.dev.ime/`.
  - Verificado nesta análise: site respondendo `HTTP 200`; containers `inscricoes-cea-app`,
    `inscricoes-cea-queue`, `inscricoes-cea-scheduler`, `inscricoes-cea-db`, `inscricoes-cea-nginx` de pé.
  - `.env` do legado: `APP_ENV=local`, `APP_DEBUG=true` → **reCAPTCHA desligado** e boleto em modo
    teste (`[TESTE - NÃO PAGAR]`) no ambiente de dev.
  - O `LEVANTAMENTO_LEGADO_VS_NOVO.md` §"Como este levantamento foi feito" confirma que a versão do
    repositório é a mesma servida em dev (comparação do formulário renderizado com as blades).
- **Sistema novo:** `/home/ayrtondouglas/ime/dev/sistema_cea` (Django), container `sistema_cea-web-1`.
- **Método:** leitura de `routes/web.php` + controllers/models/views do legado e de `urls.py` +
  views/services/models/templates do novo. Toda afirmação abaixo tem `arquivo:linha`.

---

## 3. Atores e papéis

| Ator | Legado | Novo | Observação |
|---|---|---|---|
| Público/candidato | **sem login**; só envia a ficha | `candidate` autenticado (login local **ou** Senha Única) | **Mudança por design** (nova funcionalidade) |
| Docente | `Docente` (feedback + decisão) | `teacher` (feedback + decisão) | Equivalente |
| Secretaria | `Secretaria` | `secretariat` | Equivalente |
| Administrador | `Administrador` (tudo) | `administrator` (tudo) | Equivalente |

No legado, o candidato **não tem conta nem área logada**; a autenticação existe apenas para a equipe
interna (Senha Única USP). No novo, **toda** interação com inscrição exige login
(`apps/applications/views.py:22-35`).

---

## 4. Processos do sistema LEGADO (fonte de verdade)

### 4.1 P-L1 — Inscrição pública (Projeto ou Consulta)

**Ator:** público (sem login). **Rota:** `GET /` (`MainController@index`) → `POST /applications`.

**Passo a passo:**

1. **Abrir a home.** Se não houver semestre cadastrado, exibe "Nenhum semestre foi cadastrado no
   sistema." e não mostra o formulário (`resources/views/main.blade.php:462-466`). O semestre usado é
   sempre o **mais recente** (`Semester::getLatest()`, `app/Models/Semester.php:69-74`).
2. **Escolher modalidade** (`serviceType`, radio `Consulta`/`Projeto`, `main.blade.php:27-31`).
   - Se `Projeto`: bloqueado **fora da janela de inscrição** (`start_date_enrollments`..`end_date_enrollments`).
     Bloqueio client-side (alert) e server-side (`ApplicationController.php:97-100`).
   - Se `Consulta`: **não há** bloqueio de janela no servidor.
   - `dataCollect = Não` com `Projeto` é bloqueado **apenas no JS** (`main.blade.php:698-708`).
3. **Preencher a ficha** (campos em `inscricoes-cea/docs/ANALISE_REESCRITA_DJANGO.md:224-259`):
   - Pessoais: `projectResponsible`, `contactPhone` (+`whatsapp`), `CPFCNPJ`, `email`,
     `emailConfirmation` (só JS), `institution`, `course`.
   - Vínculo/finalidade/agência/área: checkboxes múltiplos (`institutionRelationship[]`,
     `projectPurpose[]`, `fundingAgency[]`, `knowledgeArea[]`) com "Outro" condicional.
     Validação: → `required|array` para os três primeiros; `fundingAgency` é opcional
     (`StoreApplicationRequest.php:34-41`).
   - `mentor` e `declaration` obrigatórios se finalidade ∈ {IC, Mestrado, Doutorado}
     (`StoreApplicationRequest.php:67-77`).
   - Reembolso: `refundReceipt` (Sim/Não) + `refundReceiptData` (obrigatório se Sim) + dados bancários
     (`bdName`, `bdCpfCnpj`, `bdBankName`, `bdAgency`, `bdAccount`, `bdType`).
   - Aceites: `authorization` (obrigatório), `declaration`.
   - Dados do projeto: `dataCollect` + 9 itens descritivos (`projectTitle` … `expectedHelp`).
   - Anexos: `anexosNovos[newN][arquivo]`, **soma ≤ 8 MB** (só validação client-side,
     `main.blade.php:486-492`).
   - **reCAPTCHA v2** obrigatório fora de `APP_ENV=local` (`main.blade.php:448-454`;
     `ApplicationController.php:77-93`).
   - Validações client-side: e-mail/confirmação, dígito verificador CPF/CNPJ, "ao menos 1" checkbox,
     confirmação via SweetAlert (`main.blade.php:474-863`).
4. **Submeter (`POST /applications`, `ApplicationController@store:73-214`):**
   - Valida reCAPTCHA (prod) → obtém semestre mais recente → bloqueia Projeto fora da janela.
   - Gera **protocolo de 9 dígitos** com zeros à esquerda, único por checagem em loop
     (`ApplicationController.php:104-111`).
   - Concatena múltipla escolha em **CSV** (`:113-118`).
   - Cria `Application`; **`authorization`/`declaration` não são persistidos** (não são `fillable`).
   - Salva anexos sob o protocolo (`:122-135`).
   - **Status inicial** (`:137-141`):
     - Projeto → `"Aguardando agendamento da triagem"`
     - Consulta → `"Aguardando agendamento da reunião de consulta"`
   - **Gera boleto automaticamente via SOAP** (`:143-167`): Projeto **R$ 80,00** / Consulta **R$ 140,00**,
     `relativoA = "Taxa de Inscrição"`, vencimento **D+3**; falha → e-mail ao CEA.
   - Dispara e-mails (só se houver template **ativo**): CEA e inscrito (com PDF do boleto, ficha e
     anexos); se `refundReceipt=Sim`, CEA (`:171-201`).
   - Registra evento `"Inscrição"` / `"Inscrição Realizada"` (`:203-208`).
   - Flash de sucesso com o protocolo e `redirect("/")` (`:210-212`).

**Estado final:** inscrição criada com status de agendamento e boleto emitido. O candidato **só
recebe o boleto por e-mail**; não existe acompanhamento público.

**Evidências:** `routes/web.php:27,44`; `ApplicationController.php:73-214`;
`resources/views/main.blade.php`; `StoreApplicationRequest.php`.

---

### 4.2 P-L2 — Acompanhamento do candidato

**Não existe.** Não há entidade de login público, rota de consulta por protocolo, nem download de
boleto/anexo pelo candidato. O protocolo aparece uma única vez no flash de sessão
(`ApplicationController.php:210`). Anexos e comprovantes têm download **público por UUID**, sem login
(`routes/web.php:46,48`; `AttachmentController.php:12-19`).

---

### 4.3 P-L3 — Financeiro e cobranças

**Status bancário** (`bank_slips.statusBoletoBancario`, 1 char): `E`=Emitido, `P`=Pago,
`V`=Verificar, `C`=Cancelado (`app/Models/BankSlip.php:42-47`).
**Tipos** (`relativoA`): `Taxa de Inscrição`, `Taxa de Inscrição (Substituído)`, `Taxa de Projeto`,
`Taxa de Projeto (Substituído)`, `Complemento de Taxa` (`app/Models/Application.php:81-112`).
**Status agregado exibido:** `Pago` (se algum `P` ou confirmação manual), `Emitido` (algum `E` não
vencido), `Não Emitido` (sem boletos), senão o status do mais recente (`Application.php:115-169`).

**Processos internos:**

1. **Listar/gerenciar inscrições** (`applications.index`): filtro por semestre (default = mais
   recente); colunas e ações em `applications/index.blade.php:28-140` (Visualizar, PDF Completo, PDF
   1ª Página, Transferir, Excluir, "Mudar" modalidade).
2. **Regenerar boleto** (`regenerateBoleto`, `ApplicationController.php:519-554`): só se **não** existir
   `applicationFee`; gera novo (80/140) e envia `NotifyUserNewBoleto`.
3. **Confirmar pagamento manual (depósito)** (`confirmManualPayment:723-774`): só boleto não
   substituído, não `P`, não confirmado e **vencido/hoje**; grava `manual_payment_confirmed*` e evento;
   **não altera o status bancário**.
4. **Cobranças manuais / vencidos** (`overdueIndex:577-626`): lista boletos vencidos, envio em massa
   (`sendOverdueReminders:628-674`) com template `NotifyOverdueBankSlip` **ativo**, registrando evento
   `"Cobrança Manual"`.
5. **Relatório financeiro** (`FinancialReportController`): 1 linha por inscrição, com Taxa de
   Inscrição/Projeto/Complemento; **sincronização AJAX SOAP** por linha (`POST /financial-reports/{id}/sync`);
   exportação CSV (`;`, BOM) e Excel (`FinancialReportController.php:96-174`).
6. **Job agendado** a cada 15 min: registra eventos `"Taxa de inscrição"`/`"Taxa do projeto"` quando o
   boleto passa a `P` (`app/Console/Kernel.php:22-67`).

---

### 4.4 P-L4 — Triagem (aplicável só a Projeto)

**Status inicial:** `"Aguardando agendamento da triagem"` (`ApplicationController.php:138`).

1. **Agendar** (Admin/Secretaria) a partir da lista de Inscrições (ícone calendário) →
   `POST /triages` (`TriageController@store:79-108`):
   - bloqueia se `serviceType=Consulta` ("Consultas não passam pela triagem");
   - cria `Triage` (data `d/m/Y`, hora, modo `Online`/`Presencial`, link **ou** local);
   - status → `"Aguardando resultado da triagem"`;
   - e-mail `NotifyAboutTriageSchedule` (inscrito + cc CEA).
2. **Feedback docente** (só `Docente`, só **após** data/hora): radios `"Triagem Realizada"` /
   `"Triagem não realizada"` via AJAX → `PATCH /triages/feedback/{id}/update`
   (`triages/index.blade.php:61-71`; `TriageController.php:231-250`).
3. **Informar resultado** (Admin/Secretaria/Docente) → `PATCH /triages/{id}/informdecision`
   (`TriageController.php:213-229` → `TriageService::processDecision`):
   - decisões exatas: `"Aprovado como projeto"`, `"Aprovado como Consulta"`, `"Não aprovado"`;
   - o **status da inscrição vira o texto da decisão** (`TriageService.php:17`);
   - taxas: `"Aprovado como projeto"` e taxa de projeto ≠ paga → emite **Taxa de Projeto R$ 250**
     (`TriageService.php:27`); `"Aprovado como Consulta"` e sem complemento → **Complemento R$ 60**
     (`:32`); `"Não aprovado"` → nada;
   - e-mail `NotifyAboutTriageDecision`.
4. **Reagendar** (Admin/Secretaria) → `PATCH /triages/{id}/reschedule`: limpa link/local, atualiza,
   envia e-mail e evento `"reagendamento triagem"`; **não muda status** (`TriageController.php:174-211`).
5. **Cancelar** (Admin/Secretaria) → `DELETE /triages/{id}`: status volta a
   `"Aguardando agendamento da triagem"`, apaga o registro (físico), evento `"cancelamento triagem"`
   (`:150-172`).

---

### 4.5 P-L5 — Reunião de Consulta (aplicável só a Consulta)

Análogo à triagem, com diferenças:
- status inicial `"Aguardando agendamento da reunião de consulta"` (`ApplicationController.php:140`);
- feedback: `"Consulta realizada"` / `"Consulta não realizada"` (`consultationmeetings/index.blade.php:57-60`);
- decisão (`ConsultationMeetingController.php:212-247`): **apenas** `"Aprovado como projeto"` gera
  **Taxa de Projeto R$ 250**; **não há** regra de complemento R$ 60 para "Aprovado como Consulta";
- e-mails `NotifyAboutConsultationMeetingSchedule` / `...Decision`.

---

### 4.6 P-L6 — Mudança de modalidade (Admin/Secretaria)

`PATCH /applications/{id}/changeservicetype` (`ApplicationController.php:396-518`).

**Projeto → Consulta:**
- `serviceType=Consulta`, status → `"Aguardando agendamento da reunião de consulta"`.
- Calcula total pago (boletos `P`, `valorEfetivamentePago` se >0, senão `valorDocumento`) e
  `restante = 140 − totalPago`.
- Saldo ≤ 0 → **não gera boleto**, apenas alerta manual de estorno.
- Boleto atual **pago** → gera/reutiliza **Complemento de Taxa** com o restante.
- Boleto atual **não pago** → renomeia antigo para `Taxa de Inscrição (Substituído)`, tenta cancelar
  (se `E`) e gera **nova Taxa de Inscrição R$ 140**.
- Envia `NotifyServiceChange` (com BCC CEA).

**Consulta → Projeto:**
- Apenas muda `serviceType` e status para `"Aguardando agendamento da triagem"`.
- **Não recalcula taxa, não gera boleto, não notifica** (assimetria documentada).

---

### 4.7 P-L7 — Transferência de semestre

`PATCH /applications/{id}/transfer-semester` (`ApplicationController.php:310-360`):
- **Próximo semestre existe** → move, zera `transfer_pending`, reseta status para agendamento
  (triagem/consulta) e registra evento `"Transferência de Semestre"`.
- **Não existe próximo** → `transfer_pending=true` + evento `"Transferência de Semestre Pendente"`.
- Ao **criar** um semestre novo, `migratePendingApplications` move as pendentes e registra
  `"Transferência de Semestre (Automática)"` (`SemesterController.php:76-104`).

---

### 4.8 P-L8 — Exclusão lógica e restauração

- `destroy`: `deleted=true` (soft delete) + flash (`ApplicationController.php:262-276`).
- `applications/deleted`: lista excluídas do semestre mais recente; `restore`: `deleted=false`
  (`:278-308`; `applications/deleted.blade.php`).

---

### 4.9 P-L9 — Backoffice (Histórico, E-mails, Semestres, Usuários)

- **Histórico** (`GET /events`): eventos do semestre; colunas Protocolo, Nome, E-mail, Descrição, Data
  (`EventController.php:24-35`; `events/index.blade.php`).
- **E-mails** (`mailtemplates`): CRUD com Nome, Aplicação (`mail_class`), Frequência, Data/Hora, Ativo,
  Assunto, corpo (TinyMCE); ativar/desativar; **"Testar Modelo" é no-op** (`MailTemplateController::test`
  vazio). Gatilhos por evento/frequência (`mailtemplates/partials/form.blade.php:21-58`).
- **Semestres** (`semesters`): Ano, Período (`1°`/`2° Semestre`), datas letivas e janela de inscrições;
  ao criar, migra transferências pendentes.
- **Usuários** (`users`): listar/editar papéis; "Logar Como" (gate `admin` do pacote Senha Única).

---

## 5. Processos do sistema NOVO (Django) — o que o código implementa

> Nesta seção, tudo que **já existe no legado e foi reproduzido** é marcado como "equivalente";
> o que é **nova funcionalidade** é marcado como "novo".

### 5.1 N1 — Autenticação (novo)

- Rotas: `/auth/login/` (local + botão Senha Única), `/logout/` (`core/urls.py:24,35`).
- `LOGIN_URL='/auth/login/'` (`core/settings.py:158`); `AUTH_USER_MODEL=users.User` (`:123`).
- **Lacunas:** não existe **cadastro** de candidato externo (doc `TS-AUTH-002` promete, código não tem);
  **recuperação de senha** está quebrada — só existe `templates/registration/login.html`, então os
  templates do `django.contrib.auth.urls` dão `TemplateDoesNotExist`.

### 5.2 N2 — Inscrição autenticada (login antes de submeter — novo)

- `GET/POST /inscricoes/nova/` (`apps/applications/views.py:32-78`), login obrigatório.
- `ApplicationForm` (`apps/applications/forms.py`): janela de inscrição **só para Projeto**
  (`:321-335`, equivalente ao legado), `data_already_collected` obrigatório para Projeto (`:309-314`),
  autorização obrigatória (`:285-289`), anexos ≤ 8 MB por extensão/MIME (`:259-278`), CPF/CNPJ validado
  no servidor (`:240-244`), "Outro" exige texto (`:301-307`).
- **Divergência relevante:** o novo exige **uma única opção por categoria** (`:294-300`), enquanto o
  legado aceitava **múltiplas** seleções (checkboxes) por categoria.
- Criação (`apps/applications/services.py:107-213`): protocolo 9 dígitos (`:93-98`), **sempre**
  `lifecycle_status = awaiting_payment` (`:148`), `dataset_audit_required` se Projeto com dono (`:145`),
  cria taxa de inscrição (`:210-212`).
- **Não há reCAPTCHA** no sistema novo (nenhuma referência no repositório).

### 5.3 N3 — Pagamento (novo na forma; boleto já existia)

- Tela de escolha: `/pagamento/inscricao/<protocol>/` (`apps/payments/urls.py:18-21`), restrita ao dono
  e **somente à `application_fee`** (`apps/payments/views.py:41-48`).
- **Pix**: gerar/ver/QR (`apps/pix/`, gateway real `httpx`); expiração 1h; webhook idempotente
  `POST /webhooks/pix/` com `X-Token` (`apps/pix/services.py:184-267`).
- **Boleto**: gerar/ver/PDF (`apps/bank_slips/`), gateway SOAP `zeep`; sync/cancel/regenerate.
- **Pagamento manual**: `POST /pagamento/instrumento/<id>/confirmar-manual/` (Secretaria/Admin),
  exige boleto vencido (`apps/payments/services.py:303-384`).
- **Avanço do fluxo após pagar** (`apps/payments/services.py:129-154`):
  - Projeto sem taxa de projeto → `awaiting_dataset_submission`;
  - Projeto com taxa de projeto → `approved_as_project`;
  - Consulta → `awaiting_consultation_scheduling`.
- **Lacuna grave para E2E:** as telas de pagamento só operam a taxa de inscrição; **não há UI para o
  candidato pagar `project_fee`/`supplement_fee`**. Isso só é alcançável via `simulate_journey --pay`,
  admin ou serviço. Após a triagem aprovar como projeto (`awaiting_payment`), a tela mostra "Taxa paga".

### 5.4 N4 — Auditoria de dados (novo)

- Submissão por arquivo (≤10 MB) ou link externo com declaração (`apps/audits/services.py:120-167`),
  restrita a Projeto com dono e estados `awaiting_dataset_submission`/`awaiting_dataset_correction`.
- Revisão docente: `approved` / `rejected` / `needs_correction` (`:293-330`).
- Resolução administrativa: `convert_to_consultation` / `reject_application` / `transfer_term`
  (`:332-384`).
- **Lacunas:** `enable_audit` existe mas **sem rota**; o serviço **não grava `ApplicationEvent`**
  (contraria `TS-EVT-002`); notificações de auditoria existem mas **não são chamadas** pelos serviços.

### 5.5 N5/N6 — Triagem e Reunião (equivalentes)

- Triagem: `/triagens/` e `/agendamentos/triagem/<protocol>/` (`apps/meetings/`); exclusiva de
  Projeto; `online` exige link, `in_person` exige local; **feedback só após a data/hora**, por
  TEACHER; **decisão exige feedback prévio**, por SECRETARIA/ADMIN (`apps/meetings/services.py:215-218`).
- Decisão `approved_as_project` cria taxa de projeto e vai para `awaiting_payment`; `approved_as_consultation`
  cria complemento/substituição (equivalente à triagem do legado); `not_approved` terminal.
- Reunião: análoga; `approved_as_project` cria taxa de projeto **com crédito de R$ 60 → R$ 190**
  (`:560-589`) — **comportamento novo** (o legado não recalculava).
- Eventos de reunião são gravados (`meeting.*`).

### 5.6 N7 — Reembolso (novo)

- Candidato solicita (`/reembolsos/inscricao/<protocol>/solicitar/`); Secretaria aprova/executa
  (`/reembolsos/`, `/reembolsos/<id>/<action>/`) (`apps/payments/services.py:639-721`).
- **Problema óbvio:** após solicitar, o candidato é redirecionado para `payments:refund_list`
  (SECRETARIA/ADMIN) e recebe **403** (`apps/payments/views.py:207` vs `:153-161`).
- `RefundActionView` é **GET com efeito colateral** (sem CSRF).

### 5.7 N8 — Resgate de inscrição importada (novo)

- Candidato solicita (`/vincular-inscricao/`) e confirma código (`/vincular-inscricao/confirmar/`);
  Secretaria aprova manualmente (`/gestao/resgates/`) (`apps/imports/views.py:32-105`).

### 5.8 N9 — Backoffice do novo (equivalentes + lacunas)

- Listas: Inscrições (`/inscricoes/`), Excluídas (`/inscricoes/excluidas/`), Histórico
  (`/inscricoes/historico/`) — **já existem** (`apps/applications/urls.py:19-45`).
- Mudar modalidade, excluir/restaurar, transferir semestre (POST). **Transferência sem próximo
  semestre lança `TermTransferError` → 500** (`apps/applications/views.py:389-398`;
  `services.py:42-54`): **não implementa transferência pendente**.
- Cobranças vencidas + lembretes (`/cobrancas/vencidos/`), Pagamentos pendentes
  (`/pagamentos/pendentes/`), Relatórios (`/gestao/relatorios/...`), Fila de auditoria
  (`/auditoria/fila/`, `/auditoria/rejeitadas/`), Resgates.
- Períodos/E-mails/Usuários: **somente Django admin** (`templates/base/_nav.html:85-87`).

---

## 6. Matriz de processos: legado × novo

| # | Processo | Legado (verdade) | Novo (implementado) | Situação p/ E2E |
|---|---|---|---|---|
| 1 | Inscrição pública/anônima | `GET /` + `POST /applications`, sem login | exige login, `/inscricoes/nova/` | **Mudança por design** (nova) |
| 2 | Janela de inscrição (Projeto) | server + JS | server no form (`:321-335`) | Equivalente |
| 3 | Consulta fora da janela | permitida | permitida (só Projeto bloqueia) | Equivalente |
| 4 | reCAPTCHA | sim (prod) | **não existe** | Aceito (D9): login obrigatório dispensa captcha |
| 5 | Protocolo 9 dígitos | loop, sem índice único | gerador + unique | Equivalente (novo é mais seguro) |
| 6 | Múltipla escolha por categoria | permitido (CSV) | **1 opção por categoria** | **Divergência aceita (D4)** |
| 7 | Status inicial | "Aguardando agendamento triagem/consulta" | `awaiting_payment` | **Mudança por design** |
| 8 | Boleto automático no ato | sim (80/140, D+3) | não automático; candidato escolhe Pix/boleto | **Mudança por design** |
| 9 | E-mails transacionais | vários gatilhos | definidos e religados nos serviços (D6) | **Equivalente (após D6)** |
| 10 | Acompanhamento do candidato | não existe | painel `/painel/`, detalhe, pagamento | **Novo** |
| 11 | Pagamento Pix | não existe | implementado | **Novo** |
| 12 | Pagamento de taxa de projeto/complemento | boleto emitido na decisão | **UI de pagamento por taxa (D3)** | **Implementado (após D3)** |
| 13 | Confirmação manual (depósito) | só vencido; não muda status bancário | idem (exige vencido) | Equivalente |
| 14 | Regenerar boleto | só se não existe taxa | admin gera/regera | Equivalente |
| 15 | Auditoria de dados | não existe | submissão/revisão/decisão | **Novo** |
| 16 | Triagem | agendar/feedback/decisão | idem + feedback obrigatório antes da decisão | Equivalente (regra extra) |
| 17 | Reunião de consulta | idem | idem | Equivalente |
| 18 | Complemento na decisão de triagem | R$ 60 | R$ 60 | Equivalente |
| 19 | Complemento na decisão de reunião | **não gera** | não gera | Equivalente |
| 20 | Projeto→Consulta | complemento/substituição | equivalente | Equivalente |
| 21 | Consulta→Projeto | só troca tipo (sem taxa) | recalcula taxa/crédito R$ 60 | **Decisão de negócio (D2)** |
| 22 | Crédito Consulta paga → Projeto (R$ 190) | não existe | implementado | **Decisão de negócio (D2)** |
| 23 | Transferência de semestre | pendente se não há próximo | **pendente + migração automática (D5)** | **Implementado (após D5)** |
| 24 | Soft delete / restaurar | sim | sim (tela existe) | Equivalente |
| 25 | Histórico | sim | sim (`/inscricoes/historico/`) | Equivalente |
| 26 | Relatório financeiro | 1 linha/inscrição + sync SOAP | **já é 1 linha/inscrição**; sync SOAP por linha ausente | **Formato equivalente; sync opcional (D7)** |
| 27 | Cobranças/lembretes | sim | implementado | Equivalente |
| 28 | Reembolso | só aviso manual | fluxo solicitado/aprovado/executado | **Novo** |
| 29 | Resgate de inscrição | não existe | implementado | **Novo** |
| 30 | Cadastro/recuperação de senha | n/a (sem conta) | implementado (D8) | **Implementado (após D8)** |

---

## 7. Verificação da documentação existente × legado/código

> As divergências abaixo foram **fechadas** por decisão de negócio na §7.5. Consulte-a antes de
> tratar qualquer item como pendente.

### 7.1 `docs/TEST_SCENARIOS.md`

**Bate com o novo e/ou legado:** TS-APP-002/003 (criação), TS-APP-007 ("Outro" obrigatório),
TS-APP-008/009 (limite de 8 MB), TS-AUD-003/004/005 (canais de auditoria), TS-FEE-001..007 (valores),
TS-PAY-001..007, TS-PIX, TS-BSL, TS-MAN, TS-CLAIM, TS-IMP, TS-SEC (de forma geral).

**Divergências encontradas (doc ≠ código):**

1. **TS-PAY-008 (linhas 770-779)** diz que, após pagar a taxa de inscrição, o Projeto vai para
   `awaiting_screening_scheduling`. O código manda para **`awaiting_dataset_submission`**
   (`apps/payments/services.py:148-150`), coerente com o fluxo sequencial do resto do doc. **Doc
   internamente contraditória.**
2. **TS-AUTH-002 (cadastro)** e **TS-AUTH-006 (recuperação de senha)**: implementados em D8
   (`apps/users/`), com confirmação de e-mail obrigatória no login local.
3. **TS-TRM-002/003 (transferência pendente/automática)**: implementados em D5
   (`apps/applications/services.py` + `apps/terms/signals.py`).
4. **TS-NOT-*** e **TS-EVT-002**: gatilhos de notificação religados nos serviços (D6). Eventos de
   auditoria (`ApplicationEvent`) continuam sendo o ponto a validar por E2E.
5. **TS-MOD-004/005**: o novo recalcula taxas na conversão Consulta→Projeto; o **legado não fazia**.
   **Decisão D2**: a regra nova é requisito (crédito de R$ 60 / taxa de projeto R$ 190), não
   paridade com o legado.
6. **TS-AUD-016 (`enable_audit`)**: rota exposta na ficha (D10, ver §7.5).
7. **TS-REP-001/002**: relatório **já é 1 linha por inscrição** com as três taxas e cabeçalhos do
   legado (`apps/reports/services.py:81-205`); resta apenas a sincronização SOAP por linha
   (opcional). Ver correção em §7.3.

### 7.2 `docs/ARCHITECTURE.md`

- Descreve o **fluxo sequencial do Projeto** (pagar → auditar → triar) — confere com o código; é
  **diferente do legado** (proposital, nova funcionalidade).
- §25.3 (Projeto pago aprovado como Consulta → complemento R$ 60) confere com o legado.
- §25.4/§25.5 (crédito de R$ 60 na conversão Consulta→Projeto) **não têm equivalente no legado**.
- §35.6/§35.5 e §28 (transferência pendente/automática) **não estão implementados**.
- §41 e §42 (telas e rotas) divergem do código: `/entrar`, `/cadastro`, `/recuperar-senha`,
  `/gestao/periodos`, `/gestao/notificacoes`, `/inscricoes/<p>/pix/consultar` etc. não existem.
- `PaymentEvent` (§17) não existe como model; a trilha é `ApplicationEvent`.

### 7.3 `docs/LEVANTAMENTO_LEGADO_VS_NOVO.md`

- O documento é de **apresentação**, não de processo; no escopo dele, os comparativos de colunas e
  rótulos continuam majoritariamente corretos.
- **Está desatualizado em 2 itens que ele marca como P0 ausentes:**
  - "Histórico": já existe `EventListView` em `/inscricoes/historico/`
    (`apps/applications/urls.py:28`, `views.py`).
  - "Inscrições Excluídas"/"Restaurar": já existem `ApplicationDeletedListView` e `ApplicationRestoreView`
    (`apps/applications/urls.py:22-27`).
- Recomenda-se revalidar os demais itens P0 (separar Triagens/Reuniões, filtro de semestre nas telas de
  agendamento/cobrança, formato do relatório financeiro) antes de tratá-los como pendentes.
- **Correção de achado (relatório financeiro):** a redação original deste documento marcava o
  relatório como "1 linha por taxa". **Está errado.** `apps/reports/services.py:81-205` já agrupa
  **1 linha por inscrição** com as três taxas lado a lado e os cabeçalhos do legado (`:26-43`), e o
  template `templates/reports/financial_report.html:50-96` exibe as colunas corretas. Portanto D7
  **não exige reescrita**; resta apenas (opcional) a sincronização SOAP por linha
  (`/gestao/relatorios/financeiro/<protocol>/sincronizar/`).

### 7.4 `inscricoes-cea/docs/TEST_PLAN.md` (legado)

Documento **não confiável**:
- cita rota `/criar-inscricao` (inexistente — a home é `/`);
- usa valor de checkbox `"Aluno de graduação"` (o real é `"Estudante"`);
- não cobre triagem, reunião, cobranças, transferência, relatório, histórico nem e-mails;
- menciona Pix, que **não existe no legado**;
- TC06 ("Regerar Boleto" pela ficha) é inalcançável no fluxo normal, pois o botão só aparece para
  status que o código não grava e a regeneração é bloqueada quando já existe taxa.

### 7.5 Decisões de negócio (fechamento dos achados — 2026-09-25)

Decisões tomadas pelo responsável do projeto para resolver as divergências das §7.1–§7.4. Elas
**fecham o levantamento** e definem o escopo; **não** significam que o código já foi alterado.

| # | Achado (origem) | Decisão | Consequência |
|---|---|---|---|
| D1 | Alvo do E2E | **Testar apenas o sistema novo (Django).** O legado é referência de paridade, sem suíte própria. | O backlog §8.1 é referência de comportamento, não uma suíte a implementar. |
| D2 | Conversão Consulta→Projeto recalculava taxa/crédito (§7.1-5) | **Manter a regra nova** (substituição R$140→R$80 se não paga; crédito de R$60 se paga; taxa de projeto R$190). | `TS-MOD-004/005` passam a ser requisito; atualizar a doc para declarar isso como decisão (não paridade legado). |
| D3 | Candidato não paga Taxa de Projeto/Complemento (§5.3) | **Implementar UI de pagamento** dessas taxas na área do candidato. | Lacuna crítica: sem isso o happy path de Projeto não fecha; será pré-requisito do E2E. |
| D4 | Múltipla escolha por categoria (§5.2) | **Manter uma única opção por seção.** | Divergência aceita; confirmar que o legado realmente permitia múltiplas e ajustar a doc. |
| D5 | Transferência sem próximo semestre dá 500 (§5.8) | **Implementar paridade**: `transfer_pending` + migração automática na criação do semestre. | Corrige o erro 500 e habilita `TS-TRM-002/003`. |
| D6 | Notificações não são disparadas (§5.4) | **Religar todos os gatilhos do legado** (inscrição, auditoria, pagamento, agendamento, decisão, cobrança). | Habilita `TS-NOT-*`; e-mail volta a ser asserção possível no E2E. |
| D7 | Relatório financeiro em formato diferente (§7.3) | **Adotar o formato do legado**: 1 linha por inscrição com as três taxas lado a lado + sincronização SOAP. | **Correção:** o relatório já é 1 linha/inscrição (`apps/reports/services.py:81-205`); resta a sync SOAP por linha (opcional). |
| D8 | Cadastro e recuperação de senha ausentes/quebrados (§5.1) | **Implementar** cadastro de candidato externo e recuperação de senha. | Habilita `TS-AUTH-002/006`; implementado com verificação de e-mail obrigatória. |
| D9 | reCAPTCHA ausente no novo (§5.2) | **Não reintroduzir.** O formulário só pode ser preenchido por usuário autenticado, então o captcha é desnecessário. | Divergência aceita e justificada; remover a expectativa de paridade. |
| D10 | `enable_audit` sem rota (§5.4) | **Recomendação pendente**: expor na ficha para habilitar auditoria pós-resgate. | Rota `POST /auditoria/inscricao/<p>/habilitar/` + botão na ficha habilitam `TS-AUD-016`. |

**Nota pós-implementação (2026-09-25):** D3, D5, D6 e D8 foram implementados; a
correção do achado do relatório (D7) foi aplicada acima. D2 e D4 permanecem apenas
como decisões documentadas. D9 não reintroduz captcha.

**Ordem sugerida de implementação (para depois do levantamento):** D3 (destrava o happy path de
Projeto) → D7 → D6 → D5 → D8 → D2 (doc) → D4 (doc) → D9/D10.

---

## 8. Backlog de cenários E2E propostos

> **Alvo decidido (D1): apenas o sistema novo.** A seção §8.1 descreve o comportamento do legado
> como **referência de paridade** (não é uma suíte a implementar); a suíte a construir é a §8.2.

Legenda: **HP** = happy path; **OB** = problema óbvio/edge case. IDs para referência; ainda **não**
implementados (o pedido atual é só o levantamento).

### 8.1 Legado (referência de paridade — NÃO implementar; ver D1)

| ID | Tipo | Cenário | Observações |
|---|---|---|---|
| E2E-L1-01 | HP | Projeto válido → protocolo + boleto R$ 80 + status "Aguardando agendamento da triagem" | `APP_ENV=local` desliga reCAPTCHA; boleto em modo teste |
| E2E-L1-02 | HP | Consulta válida → boleto R$ 140 + status "Aguardando agendamento da reunião de consulta" | — |
| E2E-L1-03 | OB | Projeto fora da janela → flash "Fora do período de inscrição para projetos." | ajustar datas do semestre |
| E2E-L1-04 | OB | Consulta fora da janela → **permitida** (assimetria) | — |
| E2E-L1-05 | OB | `dataCollect=Não` + Projeto → alert JS e não envia | bloqueio só client-side |
| E2E-L1-06 | OB | Sem semestre cadastrado → home sem formulário | — |
| E2E-L1-07 | OB | CPF/CNPJ inválido, e-mail divergente, anexos > 8 MB | validação client-side |
| E2E-L3-01 | HP | Confirmar pagamento manual de boleto vencido | — |
| E2E-L3-02 | OB | Confirmar manual em boleto não vencido/substituído/pago → bloqueado | — |
| E2E-L3-03 | OB | Enviar lembretes sem template ativo → nada enviado | — |
| E2E-L4-01 | HP | Agendar triagem → feedback docente → decidir "Aprovado como projeto" → R$ 250 | feedback só após a data |
| E2E-L4-02 | OB | Tentar agendar triagem para Consulta → bloqueado | — |
| E2E-L4-03 | OB | Decidir "Aprovado como Consulta" tendo pago R$ 80 → complemento R$ 60 | — |
| E2E-L5-01 | HP | Agendar reunião → feedback → decidir "Aprovado como projeto" → R$ 250 | — |
| E2E-L6-01 | HP | Projeto pago → Consulta → complemento R$ 60 | — |
| E2E-L6-02 | HP | Projeto não pago → Consulta → substitui boleto por R$ 140 | — |
| E2E-L7-01 | OB | Transferir sem próximo semestre → `transfer_pending` | — |
| E2E-L8-01 | HP | Excluir e restaurar inscrição | — |
| E2E-L9-01 | HP | Histórico e relatório financeiro do semestre | sync SOAP externo |

### 8.2 Sistema novo (fluxos implementados)

| ID | Tipo | Cenário | Observações |
|---|---|---|---|
| E2E-N1-01 | HP | Login local do candidato | via `seed_e2e` |
| E2E-N1-02 | OB | "Esqueci minha senha" → hoje quebra | `TemplateDoesNotExist` |
| E2E-N2-01 | HP | Projeto válido → detalhe "Aguardando pagamento" (coberto pelo E2E_001 atual) | pagamento ainda pendente |
| E2E-N2-02 | HP | Consulta válida → detalhe "Aguardando pagamento" (E2E_002 atual) | — |
| E2E-N2-03 | OB | Projeto com `data_already_collected=false` → bloqueio (E2E_004 atual) | validação server-side |
| E2E-N2-04 | OB | Projeto fora da janela → erro no campo `term` | — |
| E2E-N2-05 | OB | Duas opções na mesma categoria → erro "Selecione apenas uma opção" | divergência vs legado |
| E2E-N3-01 | HP | Pagar taxa de inscrição por Pix + webhook | mockar gateway; `simulate_journey` |
| E2E-N3-02 | HP | Pagar taxa de inscrição por boleto | boleto exige `DEBUG=True` |
| E2E-N3-03 | HP | Secretaria confirma pagamento manual (vencido) | — |
| E2E-N3-04 | OB | Candidato tenta pagar taxa de projeto → **não há UI** | lacuna crítica |
| E2E-N4-01 | HP | Projeto pago → enviar arquivo → revisar/aprovar → `awaiting_screening_scheduling` | — |
| E2E-N4-02 | HP | Enviar link externo com declaração | — |
| E2E-N4-03 | HP | `needs_correction` → corrigir → reaprovar | — |
| E2E-N4-04 | HP | `rejected` → Secretaria converte/rejeita/transfere | — |
| E2E-N5-01 | HP | Agendar triagem → feedback (professor) → decisão (secretaria) | feedback obrigatório |
| E2E-N6-01 | HP | Agendar reunião → feedback → decisão | — |
| E2E-N7-01 | OB | Candidato solicita reembolso → **403** | bug conhecido |
| E2E-N8-01 | HP | Resgatar inscrição importada por código | — |
| E2E-N9-01 | HP | Excluir/restaurar, transferir (com próximo período existente) | — |
| E2E-N9-02 | OB | Transferir sem próximo semestre → **500** | bug conhecido |

---

## 9. Riscos e pré-requisitos para implementar os E2E

1. **Gateways externos:** Pix (`httpx`) e boleto (`zeep`/SOAP) são chamadas reais. Para E2E, usar o
   `manage.py simulate_journey` (mocka gateways e usa o caminho real do webhook) e/ou
   `services.simulate_payment` com `DEBUG=True`. Boleto exige `DEBUG=True`.
2. **Pagamento de `project_fee`/`supplement_fee` não tem UI** no candidato; o fluxo E2E completo de
   Projeto precisa de `simulate_journey --pay`, admin ou serviço.
3. **Login Senha Única** não é automatizável em dev → usar login local (`seed_e2e` cria
   `e2e_candidate`/`e2e-senha-123`) e criar usuários `teacher`/`secretariat` (não há seed no
   `seed_e2e`).
4. **Notificações não são disparadas** na maioria dos fluxos → não use e-mail como asserção principal.
5. **Feedback exige data/hora passada** e **perfis distintos** (feedback=TEACHER, decisão=SECRETARIA);
   `simulate_journey` agenda `today-1`.
6. **Base URL do E2E atual:** `http://cea.local` (`e2e/helpers.py:9`), não `localhost:8000`.
7. **E2E atual cobre só o formulário** (`e2e/test_application_e2e.py`, 7 testes) — todo o restante
   está em aberto.
8. **Legado em dev:** `APP_ENV=local`, sem reCAPTCHA e boleto em modo teste; home e formulário
   anônimos. E2E do legado valida a paridade de processos (exceto novas funcionalidades).

---

## 10. Anexos

### 10.1 Status: legado → novo

| Legado (string) | Novo (`lifecycle_status`) |
|---|---|
| `Aguardando agendamento da triagem` | `awaiting_screening_scheduling` |
| `Aguardando resultado da triagem` | `awaiting_screening_result` |
| `Aguardando agendamento da reunião de consulta` | `awaiting_consultation_scheduling` |
| `Aguardando resultado da reunião de consulta` | `awaiting_consultation_result` |
| `Aprovado como projeto` | `approved_as_project` |
| `Aprovado como Consulta` | `approved_as_consultation` |
| `Não aprovado` | `not_approved` |
| (não existia) | `awaiting_payment`, `awaiting_dataset_submission`, `awaiting_dataset_review`, `awaiting_dataset_correction`, `dataset_rejected_pending_resolution`, `submitted`, `transferred`, `canceled` |

### 10.2 Valores de taxas (iguais nos dois)

| Taxa | Valor |
|---|---:|
| Inscrição Projeto | R$ 80,00 |
| Inscrição Consulta | R$ 140,00 |
| Taxa de Projeto | R$ 250,00 |
| Complemento Projeto→Consulta / crédito Consulta→Projeto | R$ 60,00 |
| Taxa de projeto com crédito | R$ 190,00 |

### 10.3 Status bancário

`E`=Emitido, `P`=Pago, `V`=Verificar, `C`=Cancelado (`bank_slips/models.py:7-11`;
legado `app/Models/BankSlip.php:42-47`).

### 10.4 Mapa rápido de rotas (legado → novo)

| Processo | Legado | Novo |
|---|---|---|
| Inscrição | `GET /` + `POST /applications` (público) | `GET/POST /inscricoes/nova/` (logado) |
| Painel candidato | — | `GET /painel/` |
| Pagamento | boleto por e-mail | `GET /pagamento/inscricao/<p>/` |
| Pix | — | `/pagamento/inscricao/<p>/pix/...` |
| Boleto | `GET /bankslips/{id}/download` (interno) | `/pagamento/inscricao/<p>/boleto/...` |
| Auditoria | — | `/auditoria/inscricao/<p>/enviar/` |
| Lista interna | `GET /applications` | `GET /inscricoes/` |
| Excluídas | `GET /applications/deleted` | `GET /inscricoes/excluidas/` |
| Histórico | `GET /events` | `GET /inscricoes/historico/` |
| Triagem | `GET /triages` | `GET /triagens/` e `/agendamentos/...` |
| Reunião | `GET /consultationmeetings` | `GET /reunioes/` e `/agendamentos/...` |
| Cobranças | `GET /applications/overdue` | `GET /cobrancas/vencidos/` |
| Relatório | `GET /financial-reports` | `GET /gestao/relatorios/financeiro/` |
| Semestres/E-mails/Usuários | CRUD próprio | Django admin |

---

*Levantamento elaborado por leitura do código legado (fonte de verdade) e do sistema novo, com o
legado em execução para conferência. Divergências e lacunas estão explicitamente sinalizadas para
validação de negócio antes de virarem testes E2E.*
