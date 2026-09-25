# Levantamento — Sistema Legado (Laravel) × Sistema Novo (Django)

**Objetivo:** mapear como as informações são apresentadas no sistema legado e o que precisa ser
alinhado no sistema novo para que a **Secretaria** opere sem trocar de "mapa mental". O foco é
**apresentação/estrutura de informação** (telas, colunas, rótulos, ações, navegação), não CSS.

## Como este levantamento foi feito

- Ambiente legado em dev acessado em `http://inscricao.cea.dev.ime/` (o host responde em HTTP; em
  HTTPS o certificado devolve `tlsv1 unrecognized name`).
- O código-fonte do legado está no host em `/home/ayrtondouglas/ime/dev/inscricoes-cea` (bind mount
  do container `inscricoes-cea-app`, projeto compose `inscricoes-cea`). **É a mesma versão servida
  em dev** — confirmado comparando o formulário público renderizado com as blades.
- As telas autenticadas (área "Acesso Restrito") foram levantadas a partir das **blades do legado**
  (`resources/views/**`), que definem exatamente a apresentação. O login é OAuth Senha Única
  (`/login` → `https://uspdigital.usp.br/wsusuario/oauth/authorize`), interativo, e **não foi
  necessário**: a fonte local é a verdade para layout/rótulos.
- Documento companheiro já existente no legado: `docs/ANALISE_REESCRITA_DJANGO.md` (schema, regras,
  lacunas). Este documento complementa, com foco em **apresentação lado a lado**.

Legenda de prioridade: **P0** = quebra o dia a dia / função ausente; **P1** = fricção forte
(rótulo/coluna); **P2** = novo por design, só padronizar.

---

## 1. Arquitetura de informação (menu)

| Legado (sidebar "Acesso Restrito") | Novo (`templates/base/_nav.html`) | Situação |
|---|---|---|
| Página Inicial | — (logo / "Painel") | Equivalente, rótulo difere |
| Usuários (+ Logar Como) | — (apenas Django admin) | **P1** |
| Semestres | — (apenas Django admin) | **P1** |
| Histórico | — (só trilha por inscrição) | **P0** |
| Inscrições | Operação → Todas as inscrições | Equivalente, rótulo difere (**P1**) |
| Inscrições Excluidas | — | **P0** |
| Cobranças Manuais | Operação → Cobranças | Equivalente, rótulo difere (**P1**) |
| Relatório Financeiro | Relatórios → Financeiro | Equivalente, formato difere (**P0**) |
| Triagens | Operação → Agendamentos | Fundido; colunas ausentes (**P0**) |
| Reuniões de Consulta | Operação → Agendamentos | Fundido; colunas ausentes (**P0**) |
| E-mails | — (apenas Django admin) | **P1** |
| Sair | Sair | OK |

O legado usa **lista plana** de itens; o novo usa **dropdowns agrupados** ("Auditoria", "Operação",
"Relatórios"). A reorganização em si é aceitável, mas convém **renomear os itens para os nomes que a
Secretaria já conhece** (Inscrições, Triagens, Reuniões de Consulta, Cobranças Manuais, Relatório
Financeiro, Histórico, Inscrições Excluídas, Semestres, E-mails, Usuários).

---

## 2. Filtro por semestre (transversal)

No legado **quase toda tela tem "Escolher Semestre"** (modal `chooseSemester`): Inscrições,
Triagens, Reuniões de Consulta, Histórico, Relatório Financeiro, Cobranças Manuais.

No novo:
- `applications/application_list.html` tem um `<select name="term">` com "Todos os semestres".
- **Não há** filtro de semestre em: Agendamentos (`meetings`), Relatório Financeiro (`reports`),
  Cobranças (`payments:overdue_list`), Pagamentos pendentes, Fila de auditoria.

**P0** — adicionar seletor de semestre com **semestre atual como padrão** nessas telas (o legado
nunca abre "todos"; ele sempre parte do semestre vigente).

---

## 3. Mapa tela a tela (Secretaria)

### 3.1 Inscrições — listagem

| Legado `applications/index.blade.php` | Novo `applications/application_list.html` |
|---|---|
| Título "Fichas de Inscrição" + semestre | "Fichas de Inscrição" + período selecionado ✔ |
| Botão "Escolher Semestre" (modal) | `<select>` + "Buscar" (muda o padrão) |
| Colunas: Protocolo, Data da inscrição, Modalidade (+ Mudar), Nome do pesquisador, E-mail, Status, Boleto | Protocolo, Data da inscrição, Modalidade (+ Mudar), Nome do pesquisador, E-mail, Status, Boleto, **Ações** ✔ |
| Ícones de agenda (calendário) na coluna Status | Ausente (**P1**) |
| "Detalhes" / "Gerar Boleto (Manual)" por linha | "Visualizar" + botão de gerar boleto só na ficha (**P1**) |
| Ações: Visualizar, PDF Completo, PDF 1ª Página, Transferir/Pendente, Excluir | Visualizar, PDF Completo, PDF 1ª Página, Transferir, Excluir ✔ |
| Boleto: taxa/valor/status por taxa | igual ✔ (rótulos de status batem: Pago/Emitido/Cancelado/Não Emitido) |

Esta é a tela **mais alinhada**; faltam os ícones de agendamento e o botão manual por linha.

### 3.2 Ficha de Inscrição (detalhe)

| Legado `applications/show.blade.php` | Novo `applications/application_detail.html` |
|---|---|
| Título "Ficha de Inscrição" + semestre | "Inscrição {protocolo}" + badges |
| Ordem = ordem do formulário, itens **1–9 numerados com a pergunta completa** | Seções próprias ("Projeto" com rótulos **curtos**) — **P1** |
| "Protolo:" / Modalidade + "Alternar para X" | "Protocolo" / Modalidade (sem alternar; só "Mudar" na lista) — **P2** |
| "Coletou os dados" | "Dados já coletados" ✔ |
| Telefones (+ "(Whatsapp)") | Telefone + "Tem WhatsApp" ✔ |
| CPF/CNPJ — **só Admin/Secretaria** (oculto para Docente) | CPF visível a qualquer autenticado — **P1** |
| Seção financeira — **só Admin/Secretaria** | Financeiro visível a qualquer autenticado (inclusive candidato) — **P1** |
| Por boleto: Status Bancário, Valor do Documento, Data do Vencimento, Valor Pago, Data do Pagamento, "Baixar Boleto", "Confirmar Pagamento (Depósito)" | Tabela de instrumentos: #, Método, Valor, Estado, Criado, Pago em, Expira em, Ações — **P1** |
| Comprovante de depósito (se houver) | Ausente — **P1** |
| Recibo de reembolso / Dados do recibo | Seção "Recibo para reembolso" ✔ |
| Agendamentos (triagem/consulta) com badge "Dados de semestre anterior" | Seções "Triagem"/"Reunião de consulta" ✔ (sem o badge) |
| Dados bancários (nome, CPF/CNPJ, banco, agência, conta, tipo) | Dentro de "Recibo para reembolso" ✔ |
| Itens 1–9 do projeto (rótulos longos) | Itens com rótulos curtos — **P1** |
| Anexos (links) | Anexos (nome/tipo/tamanho) ✔ |
| Transferência de semestre — só Admin | Transferir semestre — Secretaria/Admin ✔ |

### 3.3 Triagens e Reuniões de Consulta → "Agendamentos"

**Legado** (`triages/index.blade.php`, `consultationmeetings/index.blade.php`) — uma tela para cada,
com "Escolher Semestre" e tabela:

| Triagens | Reuniões de Consulta |
|---|---|
| Protocolo, Nome do pesquisador, **Modalidade**, **Data**, **Local ou Link**, **Resultado**, **Taxa Projeto**, **Observações**, **Feedback** | Protocolo, Nome, **Modalidade**, **Data**, **Local ou Link**, **Resultado**, **Observações**, **Feedback** |

Ações **[Admin]**: Reagendar, Informar Resultado, Visualizar, Cancelar. Feedback do Docente
(radios "Triagem Realizada / não realizada", "Consulta realizada / não realizada") via AJAX, exibido
só após a data/hora passar.

**Novo** (`meetings/scheduling_queue.html`) — tela única "Agendamentos pendentes" com 4 tabelas:

| Fila | Colunas |
|---|---|
| Triagens de Projetos (a agendar) | Protocolo, Pesquisador, Ações |
| Reuniões de Consulta (a agendar) | Protocolo, Pesquisador, Ações |
| Triagens aguardando resultado | Protocolo, Pesquisador, Agendada, Ações |
| Reuniões aguardando resultado | Protocolo, Pesquisador, Agendada, Ações |

**P0** — faltam para a Secretaria: Modalidade, Data/hora (nas filas de agendamento), Local ou Link,
Resultado/Decisão, Observações, Taxa de Projeto (projetos), e a coluna/registro de **Feedback do
Docente** já preenchido. Recomenda-se **manter duas telas separadas** ("Triagens" e "Reuniões de
Consulta") com as colunas do legado, ou uma tela com abas mantendo as mesmas colunas.

### 3.4 Histórico (eventos)

- Legado (`events/index.blade.php`): tela "Histórico" com "Escolher Semestre" e colunas
  **Protocolo, Nome do pesquisador, E-mail, Descrição, Data**.
- Novo: só existe "Trilha de auditoria" **dentro** da ficha (Quando, Evento, Descrição, Autor).
- **P0** — recriar a tela "Histórico" por semestre (visão global de `application_events`).

### 3.5 Inscrições Excluídas

- Legado (`applications/deleted.blade.php`): Protocolo, Modalidade, Nome, E-mail + **Restaurar**.
- Novo: faz soft delete (`soft_deleted_at`) mas **não há tela nem ação de restaurar**.
- **P0** — criar "Inscrições Excluídas" com Restaurar (o modelo já tem `restore()`).

### 3.6 Cobranças Manuais

| Legado `applications/overdue_index.blade.php` | Novo `payments/overdue_list.html` |
|---|---|
| Título "Cobranças Manuais" | "Cobranças Manuais" ✔ |
| Checkbox por linha + "selecionar todos" | Ausente — **P0** |
| "Enviar e-mail de cobrança para os selecionados" | "Enviar lembretes de cobrança" (para todos) — **P0** |
| Colunas: Protocolo, Nome, E-mail, Taxa(s) Vencida(s), Valor Devido, **Histórico de Cobrança**, Ações | Protocolo, Candidato, Modalidade, Valor, Vencimento, Boleto, Ações — **P1** |
| Botão "Confirmar {relativoA}" (pagamento por depósito) por boleto | Só link "Ver boleto" (confirmação fica em outra tela) — **P1** |

### 3.7 Relatório Financeiro

| Legado `financial_reports/index.blade.php` | Novo `reports/financial_report.html` |
|---|---|
| "Escolher Semestre" | Ausente — **P0** |
| **1 linha por inscrição** | **1 linha por taxa/instrumento** — **P0** |
| Protocolo, Modalidade, Pesquisador, **CPF**, E-mail, **Dados Bancários**, **Recibo Reembolso**, **Dados Reembolso**, **Taxa de Inscrição**, **Taxa de Projeto**, **Complemento** | Protocolo, Modalidade, Candidato, E-mail, Taxa, Método, Valor base, Ajuste, Valor final, Estado, Pagamento, Manual, Substituída, Crédito, Reembolso — **P0** |
| Badges de status + **sincronização AJAX** por linha (SOAP) | Sem sincronização (dados estáticos) — **P1** |
| Exportar Excel / CSV | Exportar CSV / XLSX ✔ |

### 3.8 Semestres

- Legado (`semesters/index`, `create`, `edit`): Ano, Período, Data inicial, Data final, Data inicial
  das inscrições, Data final das inscrições + Cadastrar/Editar.
- Novo: apenas Django admin (`AcademicTermAdmin`, `admin.site`), fora do menu do sistema — **P1**.

### 3.9 E-mails (templates)

- Legado (`mailtemplates/*`): CRUD com Nome, Descrição, Frequência, Data/Hora (Única/Mensal),
  Ativo, Assunto, corpo em editor rich text; ativar/desativar; "Testar Modelo".
- Novo: modelo `NotificationTemplate` (código fixo, `is_active`) gerenciado **só no Django admin**;
  sem frequência agendada nem editor — **P1**.

### 3.10 Usuários

- Legado (`users/index`, `edit`, `loginas`): Nome, Número USP, E-mail, Perfil + Editar papéis +
  "Logar Como".
- Novo: `User` só no Django admin (`CustomUserAdmin`: username, nome, e-mail, papel, codpes…); sem
  "Logar Como" — **P1**.

---

## 4. Vocabulário (rótulos que a Secretaria vê)

Status do ciclo — alinhar o texto exibido ao legado:

| Legado (texto) | Novo (choice) | Ação |
|---|---|---|
| Aguardando agendamento da triagem | `awaiting_screening_scheduling` "Aguardando agendamento da triagem" | ✔ |
| Aguardando agendamento da reunião de consulta | idem | ✔ |
| Aguardando resultado da triagem | idem | ✔ |
| Aguardando resultado da reunião de consulta | idem | ✔ |
| Aguardando pagamento | `awaiting_payment` "Aguardando pagamento" | ✔ |
| Aguardando confirmação de pagamento | (não há choice direto; hoje via `payment_state`) | **P1** padronizar |
| Aprovado como **Consulta** | `approved_as_consultation` "Aprovado como **consulta**" | **P1** capitalização |
| Aprovado como projeto | idem | ✔ |
| Não aprovado | idem | ✔ |

Taxas: legado "Taxa de Inscrição / Taxa de Projeto / Complemento de Taxa"; novo
"Taxa de inscrição / Taxa de projeto / Taxa complementar" — **P1** padronizar ("Complemento de Taxa").

Status bancário: legado exibe letra `E/P/V/C` + agregado "Pago/Emitido/Não Emitido"; novo usa
`payment_instruments.state` (Criado/Ativo/Pago/Expirado/Cancelado/Substituído…). A coluna "Boleto"
da lista já entrega "Pago/Emitido/Cancelado/Não Emitido" — manter esse vocabulário.

---

## 5. Ficha em PDF (uso diário da Secretaria)

| Legado `applications/latex.blade.php` | Novo `documents/application_full_pdf.html` |
|---|---|
| Cabeçalho: Protocolo, **Data da inscrição**, Nome, Telefones(+Whatsapp), E-mail, Instituição/Unidade, Curso, **Vínculo**, Colaborador/orientador, **Finalidade**, **Agência**, **Área** | "Identificação": Protocolo, Nome, E-mail, Telefone, CPF, Instituição, Curso, Orientador; "Dados da Inscrição": Modalidade, Período, Status, Título — **P1** (faltam Data da inscrição e os selecionados de catálogo no topo) |
| Bloco **"A SER PREENCHIDO PELO CEA"** (Data da 1ª reunião / Decisão) | Ausente — **P1** |
| Itens **1–10** com a **pergunta completa** | Seções "Resumo do Projeto" com **rótulos curtos** e sem numeração — **P1** |
| Anexos: links ou "Não foram feitos anexos." | Ausente no PDF — **P1** |
| Logo IME/USP + rodapé CEA (LaTeX) | `_cea_header.html` / `_cea_footer.html` (WeasyPrint) ✔ |

---

## 6. Visualização de campos por perfil

| Campo | Legado | Novo | Ação |
|---|---|---|---|
| CPF/CNPJ | oculto para **Docente** | visível a qualquer autenticado | **P1** restringir |
| Financeiro (boletos/valores) | oculto para **Docente** | visível a candidato/docente | **P1** restringir |
| Ações financeiras (gerar/confirmar boleto) | só Admin/Secretaria | Secretaria/Admin ✔ | OK |

---

## 7. Itens novos por design (não existem no legado)

Login antes da inscrição, emissão e acompanhamento de **Pix**, **submissão de dados e auditoria**,
**resgates/vínculo**, **reembolsos**, **Pagamentos pendentes** e **Relatório de auditoria**. São
esperados; o pedido é apenas **padronizar rótulos e posição no menu** para não competir
conceitualmente com as telas do legado. Em especial:
- "Todas as inscrições" → renomear para **"Inscrições"**.
- "Cobranças" → **"Cobranças Manuais"**.
- "Agendamentos" → separar **"Triagens"** e **"Reuniões de Consulta"** (ou abas com os mesmos nomes).
- "Pagamentos pendentes" não tem equivalente no legado; considerar nome **"Aguardando pagamento"**
  ou integrá-lo a Cobranças, para a Secretaria não procurar em dois lugares.

---

## 8. Backlog priorizado de alinhamento

**P0 — função/visão que a Secretaria usa e que hoje não existe ou está incompleta**
1. Separar/rotular e completar colunas de **Triagens** e **Reuniões de Consulta** (Data, Local/Link,
   Resultado, Observações, Modalidade, Taxa de Projeto, Feedback).
2. **Filtro por semestre** (padrão = semestre atual) em Agendamentos, Relatório Financeiro,
   Cobranças, Pagamentos pendentes e Fila de auditoria.
3. Tela **Inscrições Excluídas** com **Restaurar**.
4. Tela **Histórico** de eventos por semestre.
5. **Relatório Financeiro** no formato 1 linha/inscrição com colunas de taxa lado a lado + CPF +
   Dados Bancários/Recibo.
6. **Cobranças Manuais**: seleção por checkbox, envio só dos selecionados, coluna "Histórico de
   Cobrança" e botão "Confirmar {taxa}".

**P1 — fricção forte**
7. Rótulos longos e numerados (1–9) na **ficha (detalhe)** e no **PDF**; incluir no PDF Data da
   inscrição, "A SER PREENCHIDO PELO CEA" e links de anexos.
8. Renomear itens do menu para o vocabulário do legado.
9. Restringir **CPF e Financeiro** a Admin/Secretaria (esconder de Docente/candidato).
10. Ficha financeira no formato do legado (Status Bancário, Valor do Documento, Vencimento, Valor
    Pago, Data do Pagamento, "Baixar Boleto", "Confirmar Pagamento (Depósito)").
11. Expor **Semestres**, **E-mails** e **Usuários** no sistema (ou atalho claro para o Django admin)
    com os rótulos/colunas do legado.
12. Padronizar rótulos: "Aprovado como Consulta", "Complemento de Taxa", "Inscrições".

**P2 — novos (só padronizar)**
13. Rótulos de menu/posição para Pix, Auditoria, Resgates, Reembolsos, Pagamentos pendentes.

---

## 9. Observações e riscos

- O login OAuth Senha Única no dev é interativo; não foram usadas credenciais. O levantamento das
  telas autenticadas vem das blades do legado (mesma versão do dev) — se houver diferença futura
  entre repositório e dev, refazer a verificação pontual.
- O `ANALISE_REESCRITA_DJANGO.md` do legado sinaliza regras de negócio (taxas, mudança de modalidade,
  transferência, status) que **não** são o foco deste documento — consultá-lo ao implementar cada
  alinhamento para não alterar comportamento.
- Antes de implementar "Triagens"/"Reuniões de Consulta" separadas, confirmar com o negócio se a
  fusão em "Agendamentos" é desejada; em caso positivo, manter as **colunas** do legado.
