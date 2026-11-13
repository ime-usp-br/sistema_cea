# TEST_SCENARIOS.md

## 1. Objetivo

Este documento descreve os cenários de teste do sistema **Inscrições CEA**.

Ele cobre:

- autenticação e contas;
- inscrição de candidatos;
- auditoria de dados de Projetos;
- pagamentos via Pix;
- pagamentos via boleto;
- pagamento manual;
- reembolsos;
- mudança de modalidade;
- transferência de período;
- triagens e reuniões de consulta;
- notificações;
- arquivos e retenção;
- resgate de inscrições importadas;
- importação de dados existentes;
- relatórios;
- eventos;
- integrações externas;
- segurança e requisitos não funcionais.

> **Convenção de IDs:** neste documento o ID usa hífen (`TS-NOT-001`); no código Python o teste usa
> underscore (`def test_TS_NOT_001_...`). Todo ID citado em nome de teste deve existir aqui — o
> meta-teste em `apps/base/tests.py` falha caso contrário. A matriz completa está em
> `docs/TEST_TRACEABILITY.md`.

---

## 2. Premissas testáveis

Os testes devem considerar as seguintes regras operacionais:

1. A página inicial exige login.
2. Candidatos acessam apenas inscrições próprias.
3. Projetos criados por usuário autenticado pagam a taxa de inscrição antes de enviar os dados para auditoria (fluxo sequencial).
4. Auditoria aceita arquivo de até 10 MB ou link externo.
5. Docente pode aprovar, rejeitar ou solicitar correção.
6. Secretaria decide auditorias rejeitadas.
7. Pix expira em 1 hora por padrão.
8. Candidato pode escolher Pix ou boleto.
9. Apenas um instrumento de pagamento ativo por taxa.
10. Pagamento manual não envia e-mail ao candidato.
11. Inscrições importadas sem dono não entram automaticamente em auditoria.
12. Resgate de inscrição importada exige confirmação por código.
13. Registros e arquivos são mantidos por prazo indeterminado.
14. Conversão de Consulta paga para Projeto gera crédito de R$ 60,00.
15. Taxa de projeto com crédito de R$ 60,00 resulta em R$ 190,00.
16. Reembolso é administrativo, não automático.

---

## 3. Convenções

### 3.1 Prefixos

| Prefixo | Módulo |
|---|---|
| `TS-AUTH` | autenticação e contas |
| `TS-APP` | inscrições |
| `TS-VAL` | validações da ficha de inscrição |
| `TS-AUD` | auditoria de dados |
| `TS-FEE` | taxas e regras financeiras |
| `TS-PAY` | orquestração de pagamento |
| `TS-PIX` | Pix |
| `TS-BSL` | boleto |
| `TS-MAN` | pagamento manual |
| `TS-REF` | reembolso |
| `TS-MOD` | mudança de modalidade |
| `TS-TRM` | transferência de período |
| `TS-MEET` | triagens e reuniões |
| `TS-NOT` | notificações |
| `TS-FILE` | arquivos |
| `TS-CLAIM` | resgate de inscrições |
| `TS-IMP` | importação |
| `TS-REP` | relatórios |
| `TS-EVT` | eventos |
| `TS-INT` | integrações |
| `TS-SEC` | segurança |
| `TS-NFR` | requisitos não funcionais |

### 3.2 Prioridades

| Prioridade | Significado |
|---|---|
| `P0` | crítico |
| `P1` | importante |
| `P2` | complementar |

---

## 4. Massa de dados recomendada

### 4.1 Usuários

| Usuário | Papel |
|---|---|
| candidato externo | `candidate` |
| candidato USP | `candidate` com identidade USP |
| docente | `teacher` |
| secretaria | `secretariat` |
| administrador | `administrator` |
| usuário sem papel | autenticado, sem acesso interno |

### 4.2 Períodos

| Período | Situação |
|---|---|
| período atual | inscrições abertas |
| período futuro | inativo |
| período encerrado | histórico |

### 4.3 Inscrições

| Inscrição | Situação |
|---|---|
| Projeto novo com dono | aguardando pagamento |
| Consulta nova com dono | aguardando pagamento |
| Projeto importado sem dono | histórico |
| Consulta importada sem dono | histórico |
| Projeto com taxa de inscrição paga | aguardando envio de dados |
| Projeto com auditoria aprovada | aguardando agendamento da triagem |
| Projeto com auditoria rejeitada | aguardando decisão |
| Projeto com taxa de projeto paga | aprovado como projeto |
| Consulta paga | pronta para reunião |

### 4.4 Taxas

| Taxa | Valor |
|---|---:|
| inscrição Projeto | R$ 80,00 |
| inscrição Consulta | R$ 140,00 |
| complemento Projeto → Consulta | R$ 60,00 |
| taxa de projeto sem crédito | R$ 250,00 |
| taxa de projeto com crédito | R$ 190,00 |

---

# 5. Cenários de autenticação e contas

## TS-AUTH-001 — Página inicial exige login

**Prioridade:** P0

**Passos:**
1. acessar `/` sem sessão autenticada.

**Resultado esperado:**
- usuário é redirecionado para login;
- nenhum formulário de inscrição é exibido.

---

## TS-AUTH-002 — Cadastro de candidato externo

**Prioridade:** P0

**Passos:**
1. acessar cadastro;
2. informar nome, e-mail e senha;
3. confirmar e-mail.

**Resultado esperado:**
- usuário criado;
- e-mail de verificação enviado;
- conta permanece limitada até confirmação.

---

## TS-AUTH-003 — Login com e-mail e senha

**Prioridade:** P0

**Resultado esperado:**
- sessão criada;
- usuário direcionado ao painel.

---

## TS-AUTH-004 — Login via Senha Única

**Prioridade:** P0

**Passos:**
1. escolher login via Senha Única;
2. autenticar no provedor;
3. retornar ao sistema.

**Resultado esperado:**
- usuário local criado ou atualizado;
- dados externos vinculados em `identity_provider_links`;
- sessão criada.

---

## TS-AUTH-005 — Vinculação de identidade existente

**Prioridade:** P1

**Pré-condição:**
- usuário local já existe com e-mail confirmado.

**Passos:**
1. autenticar via Senha Única com mesmo e-mail;
2. confirmar vinculação.

**Resultado esperado:**
- identidade vinculada ao usuário existente;
- nenhuma conta duplicada criada.

---

## TS-AUTH-006 — Recuperação de senha

**Prioridade:** P1

**Resultado esperado:**
- token expirável enviado;
- senha alterada com sucesso;
- token não pode ser reutilizado.

---

## TS-AUTH-007 — Usuário inativo

**Prioridade:** P1

**Resultado esperado:**
- login bloqueado;
- mensagem apropriada exibida.

---

# 6. Cenários de inscrições

## TS-APP-001 — Painel mostra apenas inscrições próprias

**Prioridade:** P0

**Resultado esperado:**
- candidato vê apenas inscrições com `owner_id` igual ao usuário;
- inscrições importadas sem dono não aparecem.

---

## TS-APP-002 — Criação de Projeto por candidato

**Prioridade:** P0

**Passos:**
1. candidato autenticado cria inscrição Projeto.

**Resultado esperado:**
- `origin = created_portal`;
- `owner_id` preenchido;
- `modality = project`;
- `lifecycle_status = awaiting_payment` (fluxo sequencial: o Projeto paga a taxa de inscrição antes de enviar os dados);
- `dataset_audit_required = true`;
- taxa de inscrição de R$ 80,00 criada imediatamente na submissão;
- após pagar a taxa de inscrição, a inscrição passa a `awaiting_dataset_submission`.

---

## TS-APP-003 — Criação de Consulta por candidato

**Prioridade:** P0

**Resultado esperado:**
- `modality = consultation`;
- `lifecycle_status = awaiting_payment`;
- `dataset_audit_required = false`;
- taxa de inscrição de R$ 140,00 criada.

---

## TS-APP-004 — Protocolo único

**Prioridade:** P0

**Resultado esperado:**
- protocolo possui 9 dígitos;
- protocolo é único;
- em colisão, novo protocolo é gerado.

---

## TS-APP-005 — Campos obrigatórios

**Prioridade:** P0

**Resultado esperado:**
- inscrição não é criada sem campos obrigatórios;
- mensagens de validação exibidas.

---

## TS-APP-006 — Validação de CPF/CNPJ

**Prioridade:** P1

**Resultado esperado:**
- CPF/CNPJ inválido é rejeitado;
- documento válido é aceito;
- documento salvo sem máscara.

---

## TS-APP-007 — Opções de catálogo com “Outro”

**Prioridade:** P1

**Resultado esperado:**
- seleções salvas em `application_catalog_selections`;
- opção `other` exige texto complementar;
- texto complementar armazenado em `other_text`.

---

## TS-APP-008 — Anexos de inscrição

**Prioridade:** P1

**Resultado esperado:**
- múltiplos anexos aceitos até limite total de 8 MB;
- arquivos registrados como `FileAsset`;
- propósito `application_attachment`.

---

## TS-APP-009 — Anexos acima do limite

**Prioridade:** P1

**Resultado esperado:**
- upload rejeitado;
- nenhum arquivo salvo.

---

## TS-APP-010 — Exclusão lógica

**Prioridade:** P1

**Resultado esperado:**
- inscrição excluída recebe `soft_deleted_at`;
- não aparece em listas padrão;
- pode ser restaurada.

## TS-APP-011 — Listagem global e payload válido

**Prioridade:** P1

**Resultado esperado:**
- listagem de todas as inscrições exige Secretaria/Administrador;
- payload completo de Projeto válido é aceito.

---

## TS-APP-012 — Projeto com dados não coletados

**Prioridade:** P1

**Resultado esperado:**
- inscrição de Projeto com “dados já coletados = Não” é bloqueada com mensagem clara.

---

## TS-APP-013 — Projeto sem campo descritivo

**Prioridade:** P1

**Resultado esperado:**
- falta de campo descritivo obrigatório impede o envio.

---

## TS-APP-014 — Orientador e declaração

**Prioridade:** P1

**Resultado esperado:**
- Iniciação Científica/Mestrado exigem nome do orientador e declaração;
- finalidade sem vínculo acadêmico não exige orientador.

---

## TS-APP-015 — Consulta válida completa

**Prioridade:** P1

**Resultado esperado:**
- Consulta com todos os campos obrigatórios é aceita.

---

## TS-APP-016 — Consulta sem autorização de dados

**Prioridade:** P1

**Resultado esperado:**
- ausência de autorização de uso dos dados bloqueia o envio.

---

## TS-APP-017 — Reembolso completo

**Prioridade:** P1

**Resultado esperado:**
- dados bancários e detalhes do recibo completos permitem solicitar reembolso.

---

## TS-APP-018 — Reembolso com dados incompletos

**Prioridade:** P1

**Resultado esperado:**
- omitir campo bancário ou detalhes do recibo bloqueia a solicitação.

---

## TS-APP-019 — CPF bancário inválido

**Prioridade:** P1

**Resultado esperado:**
- CPF/CNPJ bancário inválido é rejeitado.

---

## TS-APP-020 — Sem reembolso e dados bancários vazios

**Prioridade:** P2

**Resultado esperado:**
- quando não há reembolso, dados bancários podem ficar vazios.

---

## TS-APP-022 — Regressão de payload representativo

**Prioridade:** P2

**Resultado esperado:**
- payload representativo continua aceito após mudanças de validação.

---

## TS-APP-024 — Inscrição fora do período

**Prioridade:** P1

**Resultado esperado:**
- Projeto fora da janela de submissão é bloqueado;
- Consulta não é bloqueada pela janela.

---

## TS-VAL-001 — Telefone inválido é rejeitado

**Prioridade:** P1

**Resultado esperado:**
- números sem DDD, com DDD inválido ou com quantidade de dígitos incorreta são rejeitados;
- o formulário exibe a mensagem no campo de telefone.

---

## TS-VAL-002 — WhatsApp exige celular

**Prioridade:** P1

**Resultado esperado:**
- com `has_whatsapp=True`, ao menos um telefone informado deve ser celular (DDD + 9 dígitos iniciados por 9);
- caso contrário, o formulário é rejeitado.

---

## TS-VAL-003 — Nome com número ou incompleto é rejeitado

**Prioridade:** P1

**Resultado esperado:**
- o nome do pesquisador deve ser completo e não pode conter números ou símbolos estranhos.

---

## TS-VAL-004 — Confirmação de e-mail é obrigatória

**Prioridade:** P1

**Resultado esperado:**
- o campo "Repetir e-mail" é obrigatório e deve ser idêntico ao e-mail informado.

---

## TS-VAL-005 — Agência e conta aceitam somente números

**Prioridade:** P1

**Resultado esperado:**
- agência e conta com conteúdo não numérico são rejeitadas.

---

## TS-VAL-006 — Recibo e banco com conteúdo inválido

**Prioridade:** P1

**Resultado esperado:**
- dados do recibo contendo apenas símbolos são rejeitados;
- nome do banco sem letras é rejeitado.

---

## TS-VAL-007 — Erro de período de Projeto aparece na tela

**Prioridade:** P1

**Resultado esperado:**
- ao tentar enviar Projeto fora do período, o formulário continua na tela com mensagem clara;
- a tela informa que as inscrições de Projeto estão indisponíveis.

---

## TS-VAL-008 — Mensagem de sucesso após submeter

**Prioridade:** P2

**Resultado esperado:**
- após criar a inscrição, a página de detalhe exibe a mensagem de sucesso e o protocolo.

---

# 7. Cenários de auditoria de dados

## TS-AUD-001 — Projeto com dono exige auditoria

**Prioridade:** P0

**Resultado esperado:**
- Projeto criado por candidato inicia em `awaiting_payment`;
- após pagar a taxa de inscrição, o Projeto entra em `awaiting_dataset_submission`;
- `dataset_audit_required = true` e `dataset_audit_state = awaiting_submission`.

---

## TS-AUD-002 — Projeto importado sem dono não entra em auditoria

**Prioridade:** P0

**Resultado esperado:**
- `origin = imported`;
- `owner_id = NULL`;
- `dataset_audit_required = false`;
- inscrição permanece em fluxo histórico ou administrativo.

---

## TS-AUD-003 — Envio de arquivo válido

**Prioridade:** P0

**Passos:**
1. candidato envia arquivo de até 10 MB.

**Resultado esperado:**
- `dataset_audit_submissions` criada;
- `submission_channel = file`;
- `file_asset_id` preenchido;
- `external_url` nulo;
- inscrição vai para `awaiting_dataset_review`.

---

## TS-AUD-004 — Envio de arquivo acima de 10 MB

**Prioridade:** P0

**Resultado esperado:**
- upload rejeitado;
- submissão não criada.

---

## TS-AUD-005 — Envio de link externo

**Prioridade:** P0

**Passos:**
1. candidato seleciona envio por link;
2. informa URL válida;
3. declara que o link está acessível.

**Resultado esperado:**
- `submission_channel = external_link`;
- `external_url` preenchido;
- `external_link_declaration = true`;
- `file_asset_id` nulo;
- inscrição vai para `awaiting_dataset_review`.

---

## TS-AUD-006 — Link externo inválido

**Prioridade:** P1

**Passos:**
1. informar URL malformada;
2. ou informar URL com protocolo não permitido.

**Resultado esperado:**
- validação rejeita;
- submissão não criada.

---

## TS-AUD-007 — Link sem declaração de acesso

**Prioridade:** P1

**Resultado esperado:**
- submissão rejeitada;
- candidato deve confirmar declaração.

---

## TS-AUD-008 — Submissão não aceita arquivo e link simultâneos

**Prioridade:** P0

**Resultado esperado:**
- tentativa de enviar arquivo e link é rejeitada;
- apenas um canal é salvo.

---

## TS-AUD-009 — Docente solicita correção

**Prioridade:** P0

**Passos:**
1. docente analisa submissão;
2. escolhe `needs_correction`;
3. adiciona observação.

**Resultado esperado:**
- `dataset_audit_reviews.outcome = needs_correction`;
- submissão atual fica com estado `needs_correction`;
- inscrição entra em `awaiting_dataset_correction`;
- candidato é notificado.

---

## TS-AUD-010 — Candidato corrige e reenvia

**Prioridade:** P0

**Resultado esperado:**
- nova submissão criada;
- submissão anterior preservada;
- inscrição volta para `awaiting_dataset_review`.

---

## TS-AUD-011 — Docente aprova auditoria

**Prioridade:** P0

**Resultado esperado:**
- submissão vira `approved`;
- a taxa de inscrição de R$ 80,00 já foi criada na submissão e paga antes do
  envio dos dados (fluxo sequencial), não sendo duplicada na aprovação;
- inscrição vira `awaiting_screening_scheduling`;
- evento registrado.

---

## TS-AUD-012 — Docente rejeita auditoria

**Prioridade:** P0

**Resultado esperado:**
- submissão vira `rejected`;
- inscrição vira `dataset_rejected_pending_resolution`;
- secretaria precisa decidir.

---

## TS-AUD-013 — Secretaria converte em Consulta

**Prioridade:** P0

**Pré-condição:**
- auditoria rejeitada;
- Projeto com taxa de inscrição de R$ 80,00 paga (fluxo sequencial exige
  pagamento antes do envio dos dados).

**Resultado esperado:**
- modalidade vira `consultation`;
- a taxa de inscrição de Projeto (R$ 80,00) é mantida como paga;
- gerado complemento de R$ 60,00 para atingir a taxa de Consulta (R$ 140,00);
- inscrição entra em `awaiting_payment`;
- resolução registrada.

---

## TS-AUD-014 — Secretaria rejeita inscrição

**Prioridade:** P0

**Resultado esperado:**
- inscrição vira `not_approved`;
- nenhuma taxa criada se não houve pagamento;
- resolução registrada.

---

## TS-AUD-015 — Secretaria transfere de período

**Prioridade:** P1

**Resultado esperado:**
- inscrição associada ao período alvo;
- auditoria e submissões preservadas;
- resolução registra `transfer_term`.

---

## TS-AUD-016 — Auditoria habilitada após resgate

**Prioridade:** P1

**Pré-condição:**
- inscrição importada sem dono;
- candidato resgata a inscrição.

**Passos:**
1. secretaria habilita auditoria manualmente.

**Resultado esperado:**
- `dataset_audit_required = true`;
- inscrição entra em `awaiting_dataset_submission`.

---

## TS-AUD-017 — Link inacessível

**Prioridade:** P1

**Passos:**
1. docente não consegue acessar link;
2. docente solicita correção ou rejeita.

**Resultado esperado:**
- fluxo de correção ou rejeição registrado;
- candidato notificado quando aplicável.

## TS-AUD-018 — Download de arquivo de auditoria

**Prioridade:** P1

**Resultado esperado:**
- docente e Secretaria baixam o arquivo da submissão;
- candidato não acessa arquivo de terceiros;
- submissão sem arquivo retorna 404.

---

# 8. Cenários de taxas e regras financeiras

## TS-FEE-001 — Taxa de inscrição de Projeto

**Prioridade:** P0

**Resultado esperado:**
- `fee_type = application_fee`;
- `base_amount = 80.00`;
- `amount = 80.00`;
- taxa criada na submissão da inscrição (fluxo sequencial);
- aprovar a auditoria não duplica a taxa de inscrição.

---

## TS-FEE-002 — Taxa de Consulta na submissão

**Prioridade:** P0

**Resultado esperado:**
- `fee_type = application_fee`;
- `base_amount = 140.00`;
- `amount = 140.00`.

---

## TS-FEE-003 — Taxa de projeto sem crédito

**Prioridade:** P0

**Pré-condição:**
- inscrição aprovada como Projeto;
- sem crédito de modalidade.

**Resultado esperado:**
- `fee_type = project_fee`;
- `base_amount = 250.00`;
- `adjustment_amount = 0.00`;
- `amount = 250.00`.

---

## TS-FEE-004 — Taxa de projeto com crédito de Consulta paga

**Prioridade:** P0

**Pré-condição:**
- inscrição iniciou como Consulta;
- taxa de Consulta R$ 140,00 paga;
- inscrição convertida para Projeto;
- posteriormente aprovada como Projeto.

**Resultado esperado:**
- `modality_credit_amount = 60.00` ou crédito equivalente;
- `fee_type = project_fee`;
- `base_amount = 250.00`;
- `adjustment_amount = -60.00`;
- `amount = 190.00`.

---

## TS-FEE-005 — Projeto pago aprovado como Consulta

**Prioridade:** P0

**Pré-condição:**
- taxa de inscrição Projeto R$ 80,00 paga.

**Resultado esperado:**
- complemento criado com R$ 60,00;
- `fee_type = supplement_fee`;
- valor total pago passa a R$ 140,00.

---

## TS-FEE-006 — Projeto não pago aprovado como Consulta

**Prioridade:** P0

**Resultado esperado:**
- cobrança Projeto substituída;
- taxa de Consulta R$ 140,00 criada;
- nenhum complemento duplicado.

---

## TS-FEE-007 — Valor final consistente

**Prioridade:** P0

**Resultado esperado:**
- para toda `fee_requirements`:
  ```text
  amount = base_amount + adjustment_amount
  ```

---

## TS-FEE-008 — Isenção de taxa

**Prioridade:** P2

**Resultado esperado:**
- `is_waived = true`;
- `amount = 0.00` ou cobrança não gerada;
- motivo registrado.

---

# 9. Cenários de orquestração de pagamento

## TS-PAY-001 — Candidato escolhe Pix

**Prioridade:** P0

**Resultado esperado:**
- instrumento Pix criado;
- `method = pix`;
- estado `active`;
- `active_unique_fee_token` preenchido.

---

## TS-PAY-002 — Candidato escolhe boleto

**Prioridade:** P0

**Resultado esperado:**
- instrumento boleto criado;
- `method = bank_slip`;
- estado `active`;
- vencimento padrão de 3 dias.

---

## TS-PAY-003 — Troca de Pix para boleto

**Prioridade:** P0

**Pré-condição:**
- Pix ativo não pago.

**Resultado esperado:**
- Pix marcado como `superseded` ou `expired`;
- boleto ativo criado;
- apenas um instrumento ativo por taxa.

---

## TS-PAY-004 — Troca de boleto para Pix

**Prioridade:** P0

**Pré-condição:**
- boleto ativo não pago.

**Resultado esperado:**
- boleto marcado como `superseded`;
- tentativa de cancelamento externo se status `E`;
- Pix ativo criado.

---

## TS-PAY-005 — Um instrumento ativo por taxa

**Prioridade:** P0

**Resultado esperado:**
- tentativa de criar segundo instrumento ativo para mesma taxa falha;
- `active_unique_fee_token` impede duplicidade.

---

## TS-PAY-006 — Instrumento pago não pode ser substituído

**Prioridade:** P0

**Resultado esperado:**
- cobrança paga não pode ser substituída;
- operação bloqueada.

---

## TS-PAY-007 — Pix expirado permite nova geração

**Prioridade:** P0

**Resultado esperado:**
- Pix expirado vira `expired`;
- candidato pode gerar novo Pix;
- novo instrumento ativo criado.

---

## TS-PAY-008 — Pagamento confirmado libera fluxo

**Prioridade:** P0

**Para Projeto:**
- após pagamento da taxa de inscrição, inscrição vai para `awaiting_screening_scheduling`.

**Para Consulta:**
- após pagamento, inscrição vai para `awaiting_consultation_scheduling`.

---

## TS-PAY-009 — Candidato paga Taxa de Projeto/Complemento pela UI

**Prioridade:** P0

**Resultado esperado:**
- área do candidato lista as taxas não pagas;
- Taxa de Projeto e Complemento de Taxa podem ser pagas por Pix/boleto;
- taxa pendente é a selecionada por padrão.

---

## TS-PAY-010 — Taxa já paga não reabre

**Prioridade:** P1

**Resultado esperado:**
- tentar pagar novamente uma taxa paga não cria outro instrumento.

---

## TS-PAY-011 — Taxa de outra inscrição

**Prioridade:** P0

**Resultado esperado:**
- candidato não consegue pagar taxa pertencente a outra inscrição.

---

## TS-PAY-012 — Lifecycle com Taxa de Projeto pendente

**Prioridade:** P0

**Resultado esperado:**
- inscrição permanece em `awaiting_payment` enquanto a Taxa de Projeto não é paga;
- pagamento da Taxa de Projeto leva a `approved_as_project`.

---

## TS-PAY-013 — Simulação de pagamento em desenvolvimento

**Prioridade:** P1

**Resultado esperado:**
- rota de simulação só existe com `DEBUG=True`;
- confirma Pix; rejeita método manual e instrumento de terceiros.

---

## TS-PAY-014 — Cobrança em massa de boletos vencidos

**Prioridade:** P1

**Resultado esperado:**
- apenas os boletos marcados recebem cobrança;
- histórico de cobrança e evento são registrados por boleto.

---

## TS-PAY-019 — Painel de boletos vencidos

**Prioridade:** P1

**Resultado esperado:**
- Secretaria acessa a tela de Cobranças Manuais.

---

## TS-PAY-020 — Seleção de boletos vencidos

**Prioridade:** P1

**Resultado esperado:**
- serviço lista boletos vencidos e ignora pagos ou com vencimento futuro.

---

## TS-PAY-021 — Permissão da tela de cobranças

**Prioridade:** P1

**Resultado esperado:**
- candidato recebe 403; Secretaria recebe 200.

---

## TS-PAY-022 — Pagamentos pendentes

**Prioridade:** P1

**Resultado esperado:**
- painel lista inscrições com taxa a pagar;
- pagamento remove a inscrição da lista.

---

# 10. Cenários Pix

## TS-PIX-001 — Geração com payload correto

**Prioridade:** P0

**Resultado esperado:**
- requisição envia headers `X-Username` e `X-Password`;
- `valor` em formato pt-BR, exemplo `80,00`;
- `expiracao = 3600`;
- `tipoPessoa` compatível com CPF/CNPJ;
- `infoCobranca` identifica protocolo e taxa.

---

## TS-PIX-002 — Armazenamento do Pix gerado

**Prioridade:** P0

**Resultado esperado:**
- `pix_reference` salvo com `idfpix`;
- `qr_code_payload` salvo;
- imagem QR salva como `FileAsset` com propósito `pix_qrcode_image`;
- expiração registrada como geração + 1 hora.

---

## TS-PIX-003 — Consulta com parâmetro verificar

**Prioridade:** P1

**Resultado esperado:**
- sistema pode chamar `GET /pix/<idfpix>?verificar`;
- status local atualizado se pagamento confirmado.

---

## TS-PIX-004 — Webhook válido

**Prioridade:** P0

**Passos:**
1. serviço Pix envia POST com header `X-Token` válido;
2. payload contém `idfpix`, `status = Pago`, valor e data.

**Resultado esperado:**
- webhook registrado em `pix_webhook_events`;
- instrumento Pix marcado como `paid`;
- taxa marcada como paga;
- evento financeiro criado;
- fluxo da inscrição atualizado.

---

## TS-PIX-005 — Webhook com token inválido

**Prioridade:** P0

**Resultado esperado:**
- requisição rejeitada;
- pagamento não confirmado;
- evento registrado como inválido.

---

## TS-PIX-006 — Webhook duplicado

**Prioridade:** P0

**Resultado esperado:**
- segunda chamada com mesmo `idfpix` não duplica pagamento;
- resposta idempotente.

---

## TS-PIX-007 — Webhook com valor divergente

**Prioridade:** P0

**Resultado esperado:**
- pagamento não confirmado automaticamente;
- instrumento marcado como `requires_review`;
- alerta ou evento registrado.

---

## TS-PIX-008 — Webhook de Pix desconhecido

**Prioridade:** P1

**Resultado esperado:**
- payload registrado;
- nenhuma alteração de pagamento;
- erro ou alerta registrado.

---

## TS-PIX-009 — Reconciliação com listarConcluidos

**Prioridade:** P1

**Passos:**
1. rotina chama `listarConcluidos` com período válido.

**Resultado esperado:**
- período não pode ser maior que 30 dias;
- pagamentos ausentes por falha de webhook são conciliados;
- instrumentos atualizados para pago.

---

## TS-PIX-010 — Simulação de pagamento em desenvolvimento

**Prioridade:** P2

**Resultado esperado:**
- chamada `PATCH /pix/<idfpix>/simularPag` funciona apenas em dev;
- Pix passa para pago em testes.

---

## TS-PIX-011 — PDF e QR Code

**Prioridade:** P1

**Resultado esperado:**
- endpoints de PDF e QR Code retornam conteúdo válido;
- arquivos podem ser armazenados como `FileAsset` quando necessário.

---

# 11. Cenários boleto

## TS-BSL-001 — Geração de boleto registrado

**Prioridade:** P0

**Resultado esperado:**
- chamada SOAP usa headers `username` e `password`;
- método utilizado é `gerarBoletoRegistrado`;
- `valorDocumento` enviado com ponto, exemplo `80.00`;
- datas enviadas como `dd/mm/aaaa`;
- `codigoIDBoleto` salvo em `bank_slip_reference`.

---

## TS-BSL-002 — Dados obrigatórios do boleto

**Prioridade:** P0

**Resultado esperado:**
- unidade de despesa configurada;
- fonte de recurso configurada;
- estrutura hierárquica configurada;
- instruções de cobrança preenchidas;
- sacado com CPF/CNPJ apenas números.

---

## TS-BSL-003 — Consulta de situação

**Prioridade:** P0

**Resultado esperado:**
- `obterSituacao` retorna status;
- sistema converte:
  - `E` para emitido;
  - `P` para pago;
  - `V` para `requires_review`;
  - `C` para cancelado.

---

## TS-BSL-004 — Status V não confirma pagamento

**Prioridade:** P0

**Resultado esperado:**
- boleto com `V` não vira pago automaticamente;
- instrumento marcado como `requires_review`;
- secretaria pode confirmar manualmente depois.

---

## TS-BSL-005 — Boleto pago atualiza fluxo

**Prioridade:** P0

**Resultado esperado:**
- status `P` atualiza instrumento para pago;
- taxa marcada como paga;
- fluxo da inscrição liberado.

---

## TS-BSL-006 — Download de PDF

**Prioridade:** P1

**Resultado esperado:**
- `obterBoleto` retorna Base64;
- sistema decodifica corretamente;
- PDF servido ou armazenado.

---

## TS-BSL-007 — Cancelamento de boleto substituído

**Prioridade:** P1

**Pré-condição:**
- boleto emitido e não pago.

**Resultado esperado:**
- sistema tenta `cancelarBoleto`;
- boleto local marcado como `superseded` ou `canceled`.

---

## TS-BSL-008 — Consulta em lote

**Prioridade:** P1

**Resultado esperado:**
- `obterSituacaoLote` atualiza vários boletos;
- relatório financeiro usa lote para sincronização.

---

## TS-BSL-009 — Falha SOAP

**Prioridade:** P1

**Resultado esperado:**
- timeout ou fault tratado;
- erro registrado;
- nenhuma inconsistência gravada.

---

## TS-BSL-010 — Simulação de pagamento em desenvolvimento

**Prioridade:** P2

**Passos:**
1. gerar boleto com `#PAGO` em `instrucoesObjetoCobranca`.

**Resultado esperado:**
- boleto passa para `P` em até alguns minutos no ambiente de teste.

## TS-BSL-011 — Falha SOAP notifica a equipe CEA

**Prioridade:** P1

**Resultado esperado:**
- falha na geração do boleto dispara aviso para a equipe CEA;
- sucesso não dispara aviso de falha.

---

## TS-BSL-012 — Regeneração automática de boletos vencidos

**Prioridade:** P1

**Resultado esperado:**
- task regenera boletos vencidos e notifica o candidato.

---

# 12. Cenários de pagamento manual

## TS-MAN-001 — Confirmação manual de pagamento

**Prioridade:** P0

**Passos:**
1. secretaria confirma pagamento manual.

**Resultado esperado:**
- `manual_payment_confirmations` criada;
- instrumento marcado como `manual_confirmed` ou pago agregado;
- taxa considerada paga;
- evento registrado.

---

## TS-MAN-002 — Pagamento manual não altera status externo

**Prioridade:** P0

**Resultado esperado:**
- nenhum chamado externo é feito;
- status bancário original permanece inalterado.

---

## TS-MAN-003 — Pagamento manual não envia e-mail ao candidato

**Prioridade:** P0

**Resultado esperado:**
- nenhum despacho de notificação ao candidato é criado para pagamento manual;
- painel do candidato exibe status atualizado.

---

## TS-MAN-004 — Confirmação manual em instrumento pago

**Prioridade:** P1

**Resultado esperado:**
- operação bloqueada;
- confirmação duplicada não criada.

---

# 13. Cenários de reembolso

## TS-REF-001 — Solicitação de reembolso após rejeição paga

**Prioridade:** P0

**Pré-condição:**
- inscrição possui pagamento confirmado;
- inscrição é rejeitada.

**Passos:**
1. secretaria cria solicitação de reembolso.

**Resultado esperado:**
- `refund_requests` criada;
- `status = requested`;
- valor calculado corretamente.

---

## TS-REF-002 — Aprovação de reembolso

**Prioridade:** P1

**Resultado esperado:**
- `status = approved`;
- usuário aprovador registrado.

---

## TS-REF-003 — Execução de reembolso

**Prioridade:** P1

**Resultado esperado:**
- `status = executed`;
- `executed_at` preenchido;
- execução externa registrada, não automatizada.

---

## TS-REF-004 — Conversão em vez de reembolso

**Prioridade:** P0

**Pré-condição:**
- inscrição paga pode ser convertida em Consulta.

**Resultado esperado:**
- secretaria escolhe conversão;
- taxas recalculadas;
- reembolso não criado, salvo excesso.

---

## TS-REF-005 — Reembolso não pode exceder valor pago

**Prioridade:** P0

**Resultado esperado:**
- valor solicitado maior que pago é bloqueado;
- validação registra erro.

---

# 14. Cenários de mudança de modalidade

## TS-MOD-001 — Projeto não pago convertido em Consulta

**Prioridade:** P0

**Resultado esperado:**
- cobrança Projeto substituída;
- taxa de Consulta R$ 140,00 criada;
- inscrição entra em fluxo de Consulta.

---

## TS-MOD-002 — Projeto pago convertido em Consulta

**Prioridade:** P0

**Resultado esperado:**
- complemento de R$ 60,00 criado;
- nenhum novo boleto/Pix de inscrição duplicado.

---

## TS-MOD-003 — Projeto pago com valor igual ou superior a R$ 140,00

**Prioridade:** P1

**Resultado esperado:**
- nenhuma cobrança adicional criada;
- excesso registrado para análise ou reembolso.

---

## TS-MOD-004 — Consulta não paga convertida em Projeto

**Prioridade:** P0

**Resultado esperado:**
- cobrança de Consulta (R$ 140,00) substituída pela taxa de inscrição de
  Projeto (R$ 80,00) na conversão;
- inscrição Projeto entra em `awaiting_payment` (fluxo sequencial);
- após pagar a taxa de inscrição, entra em `awaiting_dataset_submission` e em
  auditoria se possuir dono;
- sem crédito de modalidade.

---

## TS-MOD-005 — Consulta paga convertida em Projeto

**Prioridade:** P0

**Resultado esperado:**
- pagamento de R$ 140,00 mantido;
- crédito de R$ 60,00 registrado;
- inscrição Projeto entra em auditoria se possuir dono;
- quando aprovada como Projeto, taxa de projeto de R$ 190,00 criada.

---

## TS-MOD-006 — Conversão de Consulta para Projeto exige auditoria quando há dono

**Prioridade:** P0

**Resultado esperado:**
- inscrição com dono vira Projeto;
- `dataset_audit_required = true`;
- se a taxa de inscrição já estiver paga, status entra em `awaiting_dataset_submission`;
- se a taxa de inscrição estiver pendente, status entra em `awaiting_payment`
  (fluxo sequencial: só envia os dados após pagar).

---

## TS-MOD-007 — Conversão de inscrição importada sem dono

**Prioridade:** P1

**Resultado esperado:**
- modalidade alterada;
- auditoria não é habilitada automaticamente;
- secretaria pode habilitar posteriormente se houver resgate.

---

# 15. Cenários de transferência de período

## TS-TRM-001 — Transferência manual com período futuro existente

**Prioridade:** P1

**Resultado esperado:**
- inscrição associada ao novo período;
- histórico preservado;
- evento registrado.

---

## TS-TRM-002 — Transferência pendente sem período futuro

**Prioridade:** P1

**Resultado esperado:**
- `transfer_pending = true`;
- evento registrado.

---

## TS-TRM-003 — Transferência automática ao criar período

**Prioridade:** P1

**Resultado esperado:**
- inscrições com `transfer_pending = true` são transferidas;
- `transfer_pending = false`;
- eventos registrados.

---

## TS-TRM-004 — Transferência preserva auditoria

**Prioridade:** P1

**Resultado esperado:**
- submissões, revisões e resoluções permanecem vinculadas;
- estado da auditoria preservado.

---

## TS-TRM-005 — Transferência preserva pagamentos

**Prioridade:** P0

**Resultado esperado:**
- taxas e instrumentos permanecem vinculados;
- pagamentos confirmados continuam válidos.

## TS-TRM-006 — Transferência manual pela Secretaria

**Prioridade:** P1

**Resultado esperado:**
- Secretaria transfere a inscrição para o próximo período disponível;
- evento `term.transferred` é registrado.

---

## TS-TRM-007 — Editar período não re-migra

**Prioridade:** P1

**Resultado esperado:**
- editar um período existente não executa a migração automática novamente.

---

# 16. Cenários de triagens e reuniões

## TS-MEET-001 — Agendar triagem para Projeto

**Prioridade:** P0

**Pré-condição:**
- inscrição Projeto paga e pronta para agendamento.

**Resultado esperado:**
- `project_screenings` criada;
- inscrição vira `awaiting_screening_result`;
- evento registrado.

---

## TS-MEET-002 — Bloquear triagem para Consulta

**Prioridade:** P0

**Resultado esperado:**
- operação bloqueada.

---

## TS-MEET-003 — Agendar reunião para Consulta

**Prioridade:** P0

**Resultado esperado:**
- `consultation_meetings` criada;
- inscrição vira `awaiting_consultation_result`.

---

## TS-MEET-004 — Bloquear reunião para Projeto

**Prioridade:** P0

**Resultado esperado:**
- operação bloqueada.

---

## TS-MEET-005 — Reunião online exige link

**Prioridade:** P1

**Resultado esperado:**
- modo `online` sem link é rejeitado.

---

## TS-MEET-006 — Reunião presencial exige local

**Prioridade:** P1

**Resultado esperado:**
- modo `in_person` sem local é rejeitado.

---

## TS-MEET-007 — Reagendar

**Prioridade:** P1

**Resultado esperado:**
- data/hora atualizados;
- estado `rescheduled`;
- evento registrado.

---

## TS-MEET-008 — Cancelar

**Prioridade:** P1

**Resultado esperado:**
- estado `canceled`;
- inscrição volta para status de agendamento pendente;
- evento registrado.

---

## TS-MEET-009 — Decisão aprovado como Projeto

**Prioridade:** P0

**Resultado esperado:**
- cria a Taxa de Projeto (R$ 250,00);
- inscrição vira `awaiting_payment` (aguarda o pagamento da Taxa de Projeto);
- após pagar a Taxa de Projeto, inscrição vira `approved_as_project`;
- se houver crédito de modalidade, valor ajustado.

---

## TS-MEET-010 — Decisão aprovado como Consulta

**Prioridade:** P0

**Resultado esperado:**
- inscrição vira `approved_as_consultation`;
- complemento criado se aplicável.

---

## TS-MEET-011 — Decisão não aprovado

**Prioridade:** P0

**Resultado esperado:**
- inscrição vira `not_approved`;
- nenhuma taxa adicional criada.

---

## TS-MEET-012 — Feedback docente após evento

**Prioridade:** P1

**Resultado esperado:**
- feedback permitido apenas após data/hora agendada;
- antes disso, operação bloqueada.

## TS-MEET-013 — Reagendamento limpa campos do modo anterior

**Prioridade:** P1

**Resultado esperado:**
- trocar online ↔ presencial limpa link/local obsoletos sem erro.

---

## TS-MEET-014 — Consulta aprovada como Projeto gera taxa

**Prioridade:** P1

**Resultado esperado:**
- decisão `approved_as_project` em Consulta cria a Taxa de Projeto.

---

## TS-MEET-015 — Alias da fila de agendamentos

**Prioridade:** P2

**Resultado esperado:**
- a rota antiga `meetings:queue` continua respondendo durante a transição.

---

# 17. Cenários de notificações

## TS-NOT-001 — Inscrição submetida

**Prioridade:** P1

**Resultado esperado:**
- candidato recebe confirmação;
- equipe CEA recebe aviso, se template ativo.

---

## TS-NOT-002 — Correção solicitada

**Prioridade:** P0

**Resultado esperado:**
- candidato recebe notificação com instrução para corrigir.

---

## TS-NOT-003 — Auditoria aprovada

**Prioridade:** P0

**Resultado esperado:**
- candidato notificado sobre próximo passo de pagamento.

---

## TS-NOT-004 — Auditoria rejeitada

**Prioridade:** P0

**Resultado esperado:**
- candidato notificado sobre rejeição;
- secretaria notificada sobre necessidade de decisão.

---

## TS-NOT-005 — Cobrança criada

**Prioridade:** P1

**Resultado esperado:**
- candidato notificado sobre Pix ou boleto disponível.

---

## TS-NOT-006 — Pagamento confirmado por Pix

**Prioridade:** P0

**Resultado esperado:**
- candidato notificado;
- despacho registrado.

---

## TS-NOT-007 — Pagamento confirmado por boleto

**Prioridade:** P0

**Resultado esperado:**
- candidato notificado;
- despacho registrado.

---

## TS-NOT-008 — Pagamento manual não notifica candidato

**Prioridade:** P0

**Resultado esperado:**
- nenhum despacho de e-mail criado para candidato;
- evento interno registrado.

---

## TS-NOT-009 — Template inativo

**Prioridade:** P1

**Resultado esperado:**
- nenhum envio realizado.

---

## TS-NOT-010 — Falha de envio

**Prioridade:** P1

**Resultado esperado:**
- despacho marcado como `failed`;
- erro registrado.

---

## TS-NOT-011 — Mudança de modalidade notifica candidato

**Prioridade:** P1

**Resultado esperado:**
- candidato recebe e-mail com a nova modalidade.

---

## TS-NOT-012 — Anexos e notificações de agendamento

**Prioridade:** P1

**Resultado esperado:**
- PDF de boleto é anexado ao e-mail;
- triagem agendada e decidida notificam o candidato.

---

## TS-NOT-013 — Reunião de consulta agendada e decidida

**Prioridade:** P1

**Resultado esperado:**
- candidato recebe e-mail no agendamento e na decisão da reunião.

---

## TS-NOT-014 — Reemissão de boleto com cópia oculta ao CEA

**Prioridade:** P1

**Resultado esperado:**
- e-mail de reemissão vai ao candidato com BCC para o centro.

---

# 18. Cenários de arquivos

## TS-FILE-001 — Arquivo de auditoria salvo com metadados

**Prioridade:** P0

**Resultado esperado:**
- `FileAsset` criado;
- propósito `dataset_submission`;
- tamanho, nome e checksum registrados.

---

## TS-FILE-002 — Download autorizado

**Prioridade:** P0

**Resultado esperado:**
- candidato baixa arquivos próprios;
- docente baixa arquivos de auditoria designados;
- secretaria/admin baixa conforme permissão.

---

## TS-FILE-003 — Download não autorizado

**Prioridade:** P0

**Resultado esperado:**
- usuário sem permissão recebe erro;
- arquivo não exposto.

---

## TS-FILE-004 — Arquivo ausente

**Prioridade:** P1

**Resultado esperado:**
- erro tratado;
- mensagem amigável;
- log registrado.

---

## TS-FILE-005 — Retenção por prazo indeterminado

**Prioridade:** P1

**Resultado esperado:**
- não há rotina automática de expurgo;
- arquivos permanecem disponíveis para auditoria.

---

## TS-FILE-006 — Link externo não é baixado

**Prioridade:** P0

**Resultado esperado:**
- sistema apenas armazena URL;
- nenhum download automático é realizado.

---

# 19. Cenários de resgate de inscrições

## TS-CLAIM-001 — Solicitação de resgate

**Prioridade:** P0

**Passos:**
1. usuário logado informa protocolo/e-mail/documento.

**Resultado esperado:**
- `legacy_ownership_claims` criada;
- status `pending` ou `code_sent`.

---

## TS-CLAIM-002 — Código enviado para e-mail registrado

**Prioridade:** P0

**Resultado esperado:**
- código enviado para `legacy_contact_email`;
- código armazenado como hash;
- expiração registrada.

---

## TS-CLAIM-003 — Código correto vincula inscrição

**Prioridade:** P0

**Resultado esperado:**
- `service_applications.owner_id` preenchido;
- claim vira `verified`;
- inscrição aparece no painel do candidato.

---

## TS-CLAIM-004 — Código incorreto

**Prioridade:** P0

**Resultado esperado:**
- vínculo não realizado;
- tentativa registrada;
- limite de tentativas aplicado.

---

## TS-CLAIM-005 — Código expirado

**Prioridade:** P1

**Resultado esperado:**
- código rejeitado;
- novo código pode ser solicitado conforme política.

---

## TS-CLAIM-006 — Nenhuma vinculação automática silenciosa

**Prioridade:** P0

**Pré-condição:**
- e-mail da conta igual ao e-mail da inscrição importada.

**Resultado esperado:**
- inscrição não é vinculada automaticamente;
- fluxo de confirmação é exigido.

---

## TS-CLAIM-007 — Aprovação manual

**Prioridade:** P1

**Resultado esperado:**
- secretaria pode vincular manualmente;
- claim vira `manually_approved`;
- usuário responsável registrado.

---

## TS-CLAIM-008 — Inscrição resgatada pode entrar em auditoria

**Prioridade:** P1

**Resultado esperado:**
- após resgate, secretaria pode habilitar auditoria;
- inscrição Projeto entra em fluxo de auditoria.

---

# 20. Cenários de importação

## TS-IMP-001 — Inscrições importadas sem dono

**Prioridade:** P0

**Resultado esperado:**
- `origin = imported`;
- `owner_id = NULL`;
- `legacy_contact_email` preservado;
- `legacy_contact_tax_id` preservado.

---

## TS-IMP-002 — Inscrições importadas não aparecem para candidatos

**Prioridade:** P0

**Resultado esperado:**
- enquanto não resgatadas, não aparecem em painel de candidato.

---

## TS-IMP-003 — Anexos importados

**Prioridade:** P0

**Resultado esperado:**
- arquivos copiados para storage;
- `FileAsset` criado;
- checksum validado;
- vínculo com inscrição preservado.

---

## TS-IMP-004 — Pagamentos preservados

**Prioridade:** P0

**Resultado esperado:**
- boletos pagos importados como pagos;
- pagamentos manuais importados como confirmados;
- cobranças substituídas preservadas.

---

## TS-IMP-005 — Projetos importados não entram em auditoria automaticamente

**Prioridade:** P0

**Resultado esperado:**
- `dataset_audit_required = false`;
- nenhum estado de auditoria iniciado automaticamente.

---

## TS-IMP-006 — Transferência de inscrição importada

**Prioridade:** P1

**Resultado esperado:**
- transferência preserva ausência de dono;
- auditoria não é habilitada automaticamente.

---

## TS-IMP-007 — Protocolos únicos na importação

**Prioridade:** P0

**Resultado esperado:**
- protocolos duplicados são detectados;
- importação reporta erro ou exceção controlada.

---

## TS-IMP-008 — Arquivos ausentes

**Prioridade:** P1

**Resultado esperado:**
- relatório de importação lista arquivos ausentes;
- inscrição pode ser importada com ressalva, se política permitir.

---

# 21. Cenários de relatórios

## TS-REP-001 — Relatório financeiro

**Prioridade:** P0

**Resultado esperado:**
- exibe taxas por inscrição;
- exibe método de pagamento;
- exibe estado agregado;
- exibe créditos de modalidade;
- exibe reembolsos solicitados.

---

## TS-REP-002 — Sincronização Pix

**Prioridade:** P0

**Resultado esperado:**
- relatório consulta Pix ativos/expirados;
- atualiza estados;
- reconciliation identifica pagos.

---

## TS-REP-003 — Sincronização boleto

**Prioridade:** P0

**Resultado esperado:**
- relatório usa consulta individual ou lote;
- estados `E`, `P`, `V`, `C` atualizados.

---

## TS-REP-004 — Exportação CSV

**Prioridade:** P1

**Resultado esperado:**
- CSV com separador `;`;
- BOM UTF-8;
- dados compatíveis com tela.

---

## TS-REP-005 — Exportação XLSX

**Prioridade:** P1

**Resultado esperado:**
- arquivo Excel válido;
- colunas financeiras corretas.

---

## TS-REP-006 — Relatório de auditoria

**Prioridade:** P1

**Resultado esperado:**
- mostra submissões;
- mostra correções;
- mostra decisões docentes e administrativas.

## TS-REP-007 — Relatório agrupado e export por semestre

**Prioridade:** P1

**Resultado esperado:**
- relatório tem uma linha por inscrição com as três taxas;
- export CSV/XLSX usa o nome `relatorio_financeiro_<ano>_<periodo>` e contém os valores.

---

# 22. Cenários de eventos

## TS-EVT-001 — Eventos de inscrição

**Prioridade:** P0

**Resultado esperado:**
- criação, exclusão lógica, transferência e mudança de modalidade geram eventos.

---

## TS-EVT-002 — Eventos de auditoria

**Prioridade:** P0

**Resultado esperado:**
- envio, correção, aprovação, rejeição e resolução geram eventos.

---

## TS-EVT-003 — Eventos financeiros

**Prioridade:** P0

**Resultado esperado:**
- criação de taxa, cobrança, pagamento, expiração, substituição, reembolso e pagamento manual geram eventos.

---

## TS-EVT-004 — Eventos de resgate

**Prioridade:** P1

**Resultado esperado:**
- solicitação, envio de código, confirmação e aprovação manual geram eventos.

---

# 23. Cenários de integrações externas

## TS-INT-001 — Timeout no Pix

**Prioridade:** P1

**Resultado esperado:**
- erro tratado;
- nenhuma cobrança inconsistente criada.

---

## TS-INT-002 — Falha SOAP no boleto

**Prioridade:** P1

**Resultado esperado:**
- fault registrado;
- usuário recebe mensagem amigável;
- sistema mantém estado íntegro.

---

## TS-INT-003 — Falha no provedor de login

**Prioridade:** P1

**Resultado esperado:**
- login não concluído;
- nenhum usuário criado sem dados válidos.

---

## TS-INT-004 — Falha de e-mail

**Prioridade:** P1

**Resultado esperado:**
- envio marcado como falho;
- nova tentativa pode ocorrer conforme política.

---

## TS-INT-005 — Falha de storage

**Prioridade:** P1

**Resultado esperado:**
- upload não confirmado;
- erro registrado;
- nenhum registro órfão invisível.

---

## TS-INT-006 — Segredos não logados

**Prioridade:** P0

**Resultado esperado:**
- logs não expõem senhas, tokens ou credenciais.

---

# 24. Cenários de segurança

## TS-SEC-001 — CSRF

**Prioridade:** P0

**Resultado esperado:**
- formulários protegidos;
- requisições sem token válido são rejeitadas.

---

## TS-SEC-002 — Webhook Pix exige token

**Prioridade:** P0

**Resultado esperado:**
- sem `X-Token` válido, pagamento não é confirmado.

---

## TS-SEC-003 — Acesso direto por URL

**Prioridade:** P0

**Resultado esperado:**
- usuário sem permissão não acessa inscrição de outro candidato;
- usuário comum não acessa áreas internas.

---

## TS-SEC-004 — Dados sensíveis

**Prioridade:** P0

**Resultado esperado:**
- CPF/CNPJ e dados financeiros completos não aparecem para papéis sem permissão.

---

## TS-SEC-005 — Links externos seguros

**Prioridade:** P1

**Resultado esperado:**
- links renderizados com `target="_blank"` e `rel="noopener noreferrer"`;
- URLs com esquemas perigosos são rejeitadas.

---

## TS-SEC-006 — Rate limiting

**Prioridade:** P1

**Resultado esperado:**
- login, recuperação de senha e resgate de inscrições possuem limite de tentativas.

---

## TS-SEC-007 — Upload malicioso

**Prioridade:** P1

**Resultado esperado:**
- tipos não permitidos são rejeitados;
- tamanho validado;
- arquivos armazenados fora de execução direta.

## TS-SEC-008 — Permissões de admin da Secretaria e Administrador

**Prioridade:** P1

**Resultado esperado:**
- Secretaria acessa Semestres e E-mails, mas não gerencia Usuários;
- Administrador acessa tudo via grupo RBAC.

---

# 25. Cenários não funcionais

## TS-NFR-001 — Acessibilidade básica

**Prioridade:** P2

**Resultado esperado:**
- campos possuem rótulos;
- erros associados aos campos;
- fluxo principal navegável por teclado.

---

## TS-NFR-002 — Responsividade

**Prioridade:** P2

**Resultado esperado:**
- telas principais utilizáveis em dispositivos menores.

---

## TS-NFR-003 — Logs estruturados

**Prioridade:** P2

**Resultado esperado:**
- ações críticas possuem contexto;
- erros de integração são rastreáveis.

---

## TS-NFR-004 — Geração de PDF com textos longos

**Prioridade:** P1

**Resultado esperado:**
- campos livres longos quebram corretamente;
- acentuação preservada;
- páginas extras geradas sem erro.

---

## TS-NFR-005 — PDF com caracteres especiais

**Prioridade:** P1

**Resultado esperado:**
- caracteres como `&`, `<`, `>`, `%`, `$`, `#`, `^`, `~` não quebram o documento.

## TS-NFR-006 — PDF com dados bancários e de reembolso

**Prioridade:** P2

**Resultado esperado:**
- PDF exibe dados bancários e de reembolso quando aplicável;
- sem recibo, esses dados não são impressos.

---

## TS-NAV-001 — Fluxo completo do candidato sem URLs manuais

**Prioridade:** P1

**Resultado esperado:**
- candidato percorre painel, inscrição, pagamento e auditoria por links.

---

## TS-NAV-002 — Fluxo de auditoria da Secretaria sem URLs manuais

**Prioridade:** P1

**Resultado esperado:**
- Secretaria percorre fila, revisão e resolução por links.

---

## TS-NAV-003 — Menu segmentado por papel

**Prioridade:** P1

**Resultado esperado:**
- cada papel vê apenas os itens de menu permitidos.

---

## TS-NAV-004 — Breadcrumbs em todas as páginas

**Prioridade:** P2

**Resultado esperado:**
- páginas exibem breadcrumb consistente.

---

## TS-NAV-005 — Links de retorno consistentes

**Prioridade:** P2

**Resultado esperado:**
- botões “Voltar” retornam à origem esperada.

---

## TS-NAV-006 — Relatórios ligam às inscrições

**Prioridade:** P2

**Resultado esperado:**
- protocolos do relatório navegam para a ficha da inscrição.

---

## TS-NAV-007 — Instrumentos ligam a boleto/Pix/recibo

**Prioridade:** P2

**Resultado esperado:**
- instrumentos financeiros ligam às telas correspondentes.

---

# 26. Regressão mínima recomendada

A regressão mínima deve incluir:

1. `TS-AUTH-001` — login obrigatório.
2. `TS-APP-002` — Projeto criado inicia aguardando pagamento (fluxo sequencial).
3. `TS-APP-003` — Consulta criada entra em pagamento.
4. `TS-AUD-003` — envio de arquivo válido.
5. `TS-AUD-005` — envio de link externo.
6. `TS-AUD-009` — docente solicita correção.
7. `TS-AUD-011` — aprovação de auditoria libera o agendamento da triagem.
8. `TS-AUD-012` — rejeição gera decisão administrativa.
9. `TS-FEE-004` — taxa de projeto com crédito de R$ 60,00 resulta em R$ 190,00.
10. `TS-PAY-005` — apenas um instrumento ativo por taxa.
11. `TS-PIX-002` — Pix gerado com expiração de 1 hora.
12. `TS-PIX-004` — webhook válido confirma pagamento.
13. `TS-PIX-005` — webhook inválido rejeitado.
14. `TS-BSL-001` — boleto registrado gerado corretamente.
15. `TS-BSL-003` — consulta de situação de boleto.
16. `TS-MAN-003` — pagamento manual não envia e-mail.
17. `TS-REF-001` — reembolso solicitado após rejeição paga.
18. `TS-MOD-005` — Consulta paga convertida em Projeto registra crédito.
19. `TS-CLAIM-003` — código correto vincula inscrição.
20. `TS-CLAIM-006` — nenhuma vinculação automática silenciosa.
21. `TS-IMP-005` — Projeto importado sem auditoria automática.
22. `TS-FILE-005` — retenção por prazo indeterminado.
23. `TS-SEC-002` — webhook exige token.
24. `TS-SEC-003` — acesso por URL validado.

---

## 27. Critérios gerais de aceite

O sistema será considerado aderente quando:

1. somente usuários autenticados acessarem inscrições;
2. Projetos com dono pagarem a taxa de inscrição antes de passarem por auditoria (fluxo sequencial);
3. auditoria aceitar arquivo ou link externo;
4. docente puder aprovar, rejeitar ou solicitar correção;
5. secretaria puder decidir auditorias rejeitadas;
6. Pix expirar em 1 hora por padrão;
7. candidato puder escolher Pix ou boleto;
8. apenas uma cobrança ativa existir por taxa;
9. webhook Pix for seguro e idempotente;
10. boletos forem gerados e consultados corretamente;
11. pagamento manual confirmar taxa sem enviar e-mail;
12. créditos de modalidade forem aplicados corretamente;
13. reembolsos forem administrativos e auditáveis;
14. inscrições importadas forem preservadas;
15. resgate exigir confirmação por código;
16. arquivos forem mantidos e rastreáveis;
17. relatórios refletirem pagamentos, créditos e reembolsos;
18. eventos permitirem auditoria completa.
