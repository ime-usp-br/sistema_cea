# Relatório de revisão do E2E — Fase 0

Data: 2026-11-23
Base: inspeção estática da suíte, três execuções na stack isolada e cruzamento com `docs/TEST_SCENARIOS.md`.

Documentos gerados nesta fase:

- `docs/E2E_COVERAGE_MATRIX.md` — métricas, lacunas e matriz por prioridade/área.
- `docs/e2e_scenario_catalog.csv` — catálogo dos 216 cenários `TS-*`.
- `docs/e2e_route_coverage.csv` — cobertura das 72 rotas não-admin.

## 1. Resumo executivo

A suíte E2E tem boa qualidade nos caminhos principais: 55 testes passam em uma stack recém-criada, cobrindo jornadas completas de Projeto/Consulta, auditoria, pagamentos, triagem/reunião, reembolso, modalidade, transferência e resgate. A infraestrutura também é correta para testes herméticos: gateways fake, Celery eager, e-mail em arquivo e Senha Única via faker.

O problema não é a qualidade do happy path, e sim a **cobertura e a repetibilidade**:

- Apenas 63 dos 216 cenários têm cobertura E2E direta (29,2%).
- 48 cenários P0 estão em lacuna e 14 são parciais.
- A segunda e a terceira execuções no mesmo banco falham por resíduos da primeira: a suíte não é idempotente.
- A suíte não roda no CI e não tem rastreabilidade para `TS-*`.
- Notificações, segurança, arquivos, navegação e validações de formulário estão praticamente ausentes do E2E.

## 2. Resultados da linha de base

| Rodada | Banco | Resultado | Duração |
|---|---|---|---|
| 1 | novo | 55 passed | 411,49 s |
| 2 | reutilizado | 54 passed, 1 failed | 401,74 s |
| 3 | reutilizado | 54 passed, 1 failed | 403,01 s |
| 4 | reutilizado | 55 passed | 597,68 s |
| 5 | mesmo banco da rodada 4 | 55 passed | 591,04 s |
| P0 | reutilizado | 10 passed | 140,41 s |
| Host | reutilizado, `127.0.0.1:18000` | 55 passed | 601,03 s |
| 6 | reutilizado, após correções da revisão | 55 passed | 601,29 s |
| 7 | reutilizado, jornadas/pagamentos UI-only | 55 passed | 558,77 s |
| 8 | reutilizado, suíte 100% UI-only | 55 passed | 489,61 s |

Fase 1 aplicada:

- candidato e período exclusivos por teste (`e2e_create_user`, `e2e_create_term --auto/--peek`);
- período explícito no formulário e no `simulate_journey --term`;
- namespace 9000–9999 para períodos de teste;
- inscrição importada rastreada e soft-deletada no cleanup;
- suíte executada duas vezes no mesmo banco sem falhas;
- 0 inscrições vivas e 0 usuários E2E ativos após o cleanup.

A falha original (antes da Fase 1) era sempre a mesma:

- `e2e/test_backoffice_e2e.py:32` — `test_E2E_TRM_001_002_003_cadastro_de_semestre_e_transferencia_pendente`.
- O teste esperava o período 2090 como corrente, mas a página exibia 2091, criado na rodada anterior.

## 3. Achados

| ID | Severidade | Achado | Evidência | Impacto |
|---|---|---|---|---|
| F-01 | P0 | E2E fora do CI | `pyproject.toml:84` exclui `e2e/`; `.github/workflows/ci.yml:61` roda só `pytest` | Regressões E2E passam despercebidas |
| F-02 | P0 | Sem rastreabilidade E2E→TS | Nenhum teste cita `TS-*`; gerador varre só `apps/**` | Cobertura não auditável |
| F-03 | P0 | Estado compartilhado entre testes e execuções | banco único, usuário único, termo global, fixtures `session` (`e2e/conftest.py:83-130`) | Ordem e histórico alteram o resultado |
| F-04 | P0 | Cleanup incompleto | `e2e_cleanup.py:66-74`; inscrição importada não rastreada (`test_remaining_processes_e2e.py:146-157`) | Resíduos e falha na rodada seguinte |
| F-05 | P1 | Setup por `simulate_journey` | `e2e/conftest.py:161-186`; `test_journeys_e2e.py:31-55` | Fluxos validados pelo comando, não pela UI |
| F-06 | P1 | Navegação e menus não testados | testes usam `page.goto` direto; TS-NAV 0/7 | Links/menus quebrados não são detectados |
| F-07 | P0 | Notificações sem cobertura | 0/14 `TS-NOT`; nenhum teste verifica destinatário/BCC/dispatch | Regressão silenciosa de e-mails |
| F-08 | P0 | Matriz de segurança incompleta | 3 testes; `TS-SEC-001` (CSRF) em lacuna | Exposição de dados/permissões |
| F-09 | P2 | Sem artefatos de falha | sem trace/vídeo/screenshot/JUnit | Diagnóstico caro |
| F-10 | P2 | Padrões de flakiness | `not_to_have_url` imediato (`e2e/conftest.py:145`), datas relativas | Falhas intermitentes |
| F-11 | P2 | Manutenção | helpers duplicados, `__import__("re")`, sem page objects | Custo de evolução |
| F-12 | P1 | Documentação divergente | `LEVANTAMENTO_PROCESSOS_E2E.md:294-296,323-338,553-555` | Decisões baseadas em dados velhos |
| F-13 | P2 | Asserções fracas | vários testes só comparam texto na tela | Efeitos colaterais não verificados |
| F-14 | P2 | Só Chromium desktop | `e2e/pytest.ini:3` | Sem cobertura móvel/acessibilidade |
| F-15 | P1 | Fronteiras temporais ausentes | janela de inscrição, expiração Pix, feedback no limite | Casos de borda não testados |
| F-16 | P2 | Testes agrupam vários IDs | `E2E_AUD_003_009_010_011`, `E2E_REF_001_002_003` | Falha não localiza o cenário |
| F-17 | P2 | Socket Docker montado no container E2E | `docker-compose.e2e.yml:132-134`; `e2e/conftest.py:43-71` | Acoplamento ao host e risco em CI |
| F-18 | P0 | Execuções não são idempotentes | rodadas 2 e 3 falham no mesmo teste | Suíte não é confiável fora de banco limpo |
| F-19 | P1 | Premissa de “termo mais recente” | `test_backoffice_e2e.py:26-39` | Quebra com resíduo de termos |
| F-20 | P1 | Retenção impede limpeza de termos | `e2e_cleanup.py:66-74` mantém termo com soft-deleted | Resíduo permanente no banco |
| F-21 | P2 | Marcador `e2e` declarado e não usado | `e2e/pytest.ini:5` | Impossível separar camadas |
| F-22 | P2 | Web E2E não monta o código | `docker-compose.e2e.yml:56-60` (sem volume) | Código stale se não reconstruir |

Status após a Fase 1:

- **Corrigidos**: F-01 (workflow `e2e.yml`), F-02 (comentários `# Cobre` + gerador), F-03/F-04/F-18/F-19/F-20 (isolamento por candidato/termo, namespace, rastreio da importada e purga do namespace) e F-09 (JUnit, trace e screenshot no CI).
- **Parcialmente mitigados**: F-17 (CI em host, sem socket dentro do container; o modo local em container continua disponível) e F-05/F-06 (marcadores e P0 criados; a reescrita UI-only permanece).
- **Pendentes**: F-07, F-08, F-10..F-16.

Correções da revisão de código:

- `e2e_create_user` agora cria apenas candidato, recusa username/e-mail duplicado e nunca promove conta existente ou cria superusuário.
- `e2e_create_term --auto` repete a alocação quando outra execução cria o mesmo ano.
- `e2e_cleanup --purge-e2e-terms` remove inscrições e períodos do namespace ao final da sessão, permitindo que execuções repetidas voltem a usar 9000+. A validação sobre os resíduos reais removeu 42 inscrições e 40 períodos, deixando o namespace em 0.
- As portas de host saíram do compose base para `docker-compose.e2e.host.yml`, usado apenas no CI/modo host.
- `E2E_HOST_ROOT` foi removido do workflow por não ter consumidor.

## 4. Análise da falha de repetição

Sequência observada:

1. A rodada 1 cria os termos 2090 e 2091 e várias inscrições.
2. O cleanup marca as inscrições como excluídas, mas mantém os termos porque eles ainda possuem inscrições (inclusive soft-deleted).
3. A rodada 2 cria 2090 novamente; porém o formulário usa o período mais recente, que ainda é 2091.
4. A asserção em `test_backoffice_e2e.py:32` falha.
5. A inscrição importada do teste de resgate não é rastreada, permanece ativa e reforça a retenção do termo.

Evidência do banco após a rodada 2:

```text
2027 first  all=68 live=0
2036 first  all=4  live=0
2042 first  all=2  live=0
2091 first  all=11 live=2
```

As duas inscrições ativas eram as importadas das rodadas 1 e 2, ambas com dono `e2e_candidate` e status `submitted`.

## 5. Riscos

1. **Falso verde**: um banco limpo esconde dependências de ordem; o CI pode falhar de forma intermitente conforme o volume de dados.
2. **Cobertura ilusória**: 55 testes parecem abrangentes, mas 55% dos cenários estão em lacuna.
3. **Regressão de notificações**: os serviços já disparam e-mails, mas nenhum teste verifica destinatário/BCC.
4. **Segurança**: a matriz de acesso é parcial; um erro de permissão em rota não coberta passaria.
5. **Documentação**: o levantamento desatualizado pode induzir decisões erradas sobre o que “já está coberto”.

## 6. Decisões aprovadas

| ID | Decisão aprovada | Consequência |
|---|---|---|
| D-01 | Dados únicos por teste | Cada teste cria usuários, termos e protocolos exclusivos e limpa ao final. A suíte deixa de depender do “termo mais recente” e fica apta a paralelização futura. |
| D-02 | Atualizar o cenário | `TS-AUTH-001` passa a descrever landing pública e `/painel/` protegido. Nenhuma mudança de produto. |
| D-03 | Implementar rate limiting | Perfis por rota com Redis e resposta 429; `TS-SEC-006` passa a ser E2E-UI/API. Escopo de aplicação, fora da infraestrutura de teste. |
| D-04 | E2E-CLI para importação | Os oito `TS-IMP-*` serão exercitados pelo comando real, usando uma fixture JSON sintética e versionada. |
| D-05 | UI em toda jornada | `simulate_journey` deixa de montar etapas de negócio; só pode preparar dados externos ao fluxo (ex.: usuário, período, anexo). Pagamento, auditoria, agendamento e decisão passam pela UI. |
| D-06 | P0 no PR + nightly completo | P0 no PR com meta de 7 min; suíte integral no nightly com meta de 20 min. |

### 6.1 Efeitos no escopo

- **D-05 aumenta a duração**: a suíte atual leva ~10 min (após o isolamento por teste); a versão UI-only será mais lenta. O nightly de 20 min deve absorver a suíte completa e o PR fica com o P0 (2 min 20 s medidos).
- **D-01 é pré-requisito de D-05**: sem dados exclusivos, jornadas UI-only em paralelo colidem em termos, protocolos e usuários.
- **D-03 não bloqueia a Fase 1**: o rate limiting pode ser implementado em etapa isolada, mas o cenário permanece `Lacuna` até lá.
- **D-02 altera documentação, não produto**: o ajuste deve ser feito em `docs/TEST_SCENARIOS.md` e no catálogo.

### 6.2 Ordem de implementação

1. ~~Isolamento por teste (D-01/ISO-01/ISO-02)~~ — concluído.
2. ~~Correção do rastreamento da inscrição importada e do cleanup~~ — concluído; duas rodadas completas verdes.
3. ~~Marcador P0 e gate de CI com pytest no host~~ — concluído.
4. ~~Comentários `# Cobre: TS-*` e gerador de rastreabilidade~~ — concluído.
5. ~~Reescrita das jornadas para UI-only (D-05)~~ — concluído. Todos os 55 testes criam e avançam pela UI; `simulate_journey` não é mais usado no E2E.
6. Rate limiting (D-03/RL-01/RL-02) em alteração isolada de produto.
7. E2E-CLI de importação (D-04/IMP-01).
8. ~~Atualização de `TEST_SCENARIOS.md` para `TS-AUTH-001`~~ — concluído.

### 6.3 Decisões de implementação aprovadas

| ID | Decisão | Detalhe |
|---|---|---|
| RL-01 | Perfis por rota | Login 5/min por IP+usuário; webhook Pix 60/min por IP; downloads/PDF 30/min por usuário; demais POSTs 20/min por usuário; janela de 1 min; limites por env. |
| RL-02 | Redis + 429 | Contadores em Redis, resposta 429 com `Retry-After` e headers de limite; thresholds por env; E2E usa limites baixos para provocar o bloqueio. |
| ISO-01 | Namespace E2E + limpeza | Anos 9000–9999; e-mails `e2e.candidate.<run>@example.com`; protocolos rastreados; `e2e_cleanup --purge-e2e-terms` limpa o namespace ao final; inscrições fora dele continuam soft-deleted. |
| ISO-02 | Candidato único | Candidato, inscrições e e-mails isolados por teste; docente, secretaria e admin vêm do seed compartilhado. |
| CI-01 | P0 7 min / nightly 20 min | O PR executa um smoke P0 enxuto; o nightly executa a suíte integral. |
| CI-02 | Host pytest no CI | Playwright instalado no runner; comandos de management via `docker compose exec`; sem socket Docker dentro do container E2E. |
| IMP-01 | JSON sintético | Fixture JSON pequena e versionada para `import_legacy_data`, com storage de anexos e sem dados pessoais. |
| TRACE-01 | Comentário `# Cobre: TS-*` | O gerador lê o marcador; um teste pode cobrir vários IDs sem renomear a função. |

### 6.4 Riscos das decisões

- **CI-01 é agressivo**: a linha de base completa já leva ~7 min; o P0 precisa ser um subconjunto bem menor e o build da stack fica fora do passo de teste. O P0 do PR precisará de stack com imagens em cache e um subconjunto realmente pequeno; se a meta não for atingível, o limite deve ser revisto com dados.
- **CI-02 tira o container da equação**: o runner precisa instalar Playwright/Chromium e manter Docker disponível para `docker compose exec`.
- **ISO-01 implementado**: o formulário aceita `term` via campo oculto, o `simulate_journey` recebeu `--term` e o alocador `e2e_create_term --auto/--peek` usa o namespace 9000–9999.
- **D-05 aumenta o nightly**: a meta de 20 min exige medir e possivelmente dividir a suíte por grupos ou paralelizar.

## 7. Backlog priorizado

### P0

1. ~~Tornar a suíte idempotente~~ — concluído com namespace E2E, candidato único e rastreio da importada.
2. ~~Criar job E2E no CI~~ — concluído em `.github/workflows/e2e.yml` (P0 no PR, completo no nightly).
3. ~~Adicionar comentários `# Cobre: TS-*` e atualizar o gerador~~ — concluído; 54 dos 55 testes têm marcador e 195 cenários aparecem na matriz.
4. Implementar a matriz de notificações (destinatário, BCC, dispatch).
5. Implementar a matriz de segurança (CSRF, IDOR por rota, perfis, upload).
6. Cobrir as lacunas P0 de pagamentos: troca de instrumento, um ativo por taxa, instrumento pago, Pix expirado, taxa de outra inscrição.
7. Cobrir as lacunas P0 de auditoria/arquivos: arquivo >10 MB, link inválido, ambos canais, download autorizado/negado.

### P1

- Validações da ficha (`TS-VAL-*`) e campos de reembolso (`TS-APP-016..020`).
- Variantes de modalidade e transferência (`TS-MOD-001..003`, `TS-TRM-004/005/007`).
- Bloqueios e validações de triagem/reunião (`TS-MEET-002/004/005/006/013/015`).
- Boleto: situação, status V, cancelamento, lote, falha SOAP.
- Resgate: código incorreto/expirado, fila de aprovação, auditoria após resgate.
- Navegação por papel e links (`TS-NAV-001..007`).
- Fronteiras temporais e janela de inscrição.

### P2

- Acessibilidade, responsividade e matriz de navegadores.
- Artefatos de falha, retries controlados e relatório JUnit/HTML.
- Refatoração de helpers/page objects.
- Cobertura das telas administrativas (usuários, papéis, templates, permissões da secretaria).

## 8. Critérios de aceite da revisão

1. 216/216 cenários classificados e com status no catálogo.
2. 100% dos P0 com E2E ou waiver aprovado.
3. Toda rota não-admin coberta ou com isenção registrada.
4. Toda notificação com destinatário, BCC e dispatch assertados.
5. Matriz de acesso por perfil cobrindo todas as rotas sensíveis.
6. Três execuções verdes consecutivas no mesmo banco, sem resíduos.
7. Suíte no CI com artefatos e tempo máximo acordado.
8. `TEST_TRACEABILITY.md` incluindo a camada E2E.

## 9. Entregas

Fase 0:

- Linha de base de três execuções documentada, com falha reproduzida e causa isolada.
- Catálogo de 216 cenários (`docs/e2e_scenario_catalog.csv`).
- Matriz de 72 rotas (`docs/e2e_route_coverage.csv`).
- Matriz de cobertura e métricas (`docs/E2E_COVERAGE_MATRIX.md`).
- Este relatório de revisão.

Fase 1:

- Isolamento por candidato/período com `e2e_create_user` e `e2e_create_term --auto/--peek`.
- `simulate_journey --term` e helper `set_application_term`.
- Cleanup rastreando a inscrição importada.
- `.github/workflows/e2e.yml` com P0 (7 min) e nightly (20 min).
- Marcadores `# Cobre: TS-*` em 54 dos 55 testes e `@pytest.mark.p0` em 10.
- `TEST_TRACEABILITY.md` regenerado com a camada E2E.
- Duas execuções completas verdes no mesmo banco e uma em modo host.

Nenhuma regra de negócio foi alterada; as mudanças de aplicação são comandos de apoio ao E2E e o parâmetro `--term` do simulador.
