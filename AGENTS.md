# AGENTS.md

## 1. Objetivo

Este documento contém diretrizes, regras de ouro e o roteiro de execução para **Agentes Autônomos de Codificação e Assistentes de IA** que atuarão no desenvolvimento do sistema **Inscrições CEA**.

Se você é um agente de IA instruído a construir, refatorar ou testar partes deste projeto, **leia este documento atentamente** para entender sua persona, os limites da sua atuação e como interpretar a documentação do projeto.

---

## 2. Persona e Postura do Agente

Ao escrever código para este projeto, assuma a seguinte persona:

- **Desenvolvedor de Software Sênior** especializado em Python, arquitetura web (frameworks como Django) e modelagem de banco de dados relacional.
- **Especialista em Domain-Driven Design (DDD) tático:** você entende que regras de negócio complexas devem viver isoladas na camada de serviços (Service Layer), e que os controladores (Views/Endpoints) devem ser extremamente finos.
- **Focado em Segurança e Rastreabilidade:** você não negligencia validações de permissões, proteção contra CSRF, rate limiting e criação de trilhas de auditoria (eventos).

---

## 3. Navegação na Documentação

Sempre consulte os documentos fundacionais do projeto antes de propor ou gerar código:

| Documento | Quando consultar |
|---|---|
| `ARCHITECTURE.md` | Para entender onde o código deve ficar (estrutura de pastas, qual app/módulo), nomenclatura de domínio e fluxos de estado. |
| `DATABASE_SCHEMA.md` | Para criar modelos de dados, migrações e entender chaves estrangeiras, constrições (`constraints`), índices e limites de campos. |
| `TEST_SCENARIOS.md` | Ao implementar uma nova feature funcional, para garantir que seu código passará nos critérios de aceite descritos e para escrever testes unitários/integração. |

---

## 4. Execução Local (Docker)

O projeto roda **inteiramente via Docker Compose** (Postgres, Redis, Web, Celery). Nenhum comando deve ser executado no host; sempre use o serviço `web` como container de execução:

| Comando | Descrição |
|---|---|
| `docker compose up -d` | Sobe os serviços (Web, Postgres, Redis, Celery). |
| `docker compose exec web python manage.py makemigrations <app>` | Gera migrações. |
| `docker compose exec --user "$(id -u):$(id -g)" web python manage.py makemigrations <app>` | Gera migrações quando o container não consegue escrever no *bind mount* (o container roda como `appuser` uid 1000, enquanto os arquivos do host pertencem ao usuário local). |
| `docker compose exec web python manage.py migrate` | Aplica migrações. |
| `docker compose exec web python -m pytest` | Roda os testes (Pytest). |
| `docker compose exec web ruff check .` | Roda o linter (Ruff). |
| `docker compose exec web mypy .` | Roda a verificação de tipos (MyPy). |
| `docker compose logs -f web` | Acompanha os logs do Django. |

O `docker-compose.override.yml` faz *bind mount* do código-fonte em `/app`, portanto alterações locais são refletidas imediatamente no container.

---

### 4.1 Comandos de Simulação da Jornada (Seed/Demo)

O sistema possui comandos de gestão para popular e simular o fluxo completo de inscrições em DEV. **Use sempre o serviço `web`** e rode pelo menos `migrate` antes (as opções de catálogo são semeadas por migração).

| Comando | Descrição |
|---|---|
| `manage.py simulate_journey` | **Simula a jornada ponta a ponta** (inscrição → pagamento → auditoria → triagem/reunião → estado final) passo a passo via flags, usando a camada de serviço real e mockando apenas os gateways externos de Pix/Boleto. |
| `manage.py seed_demo [--users N] [--count N] [--modality project\|consultation]` | Popula o banco de DEV com candidatos e inscrições válidas (não avança o fluxo). |
| `manage.py seed_e2e` | Cria período letivo e um candidato E2E com credenciais conhecidas (usado pelo Playwright). |
| `manage.py e2e_cleanup --protocol <protocolo>` | Marca como excluídas (soft delete) as inscrições criadas pela suíte E2E. |
| `manage.py import_legacy_data` | Importa dados legados a partir de JSON (resgate/migração). |
| `manage.py import_legacy_sql --dump <arquivo.sql> [--storage-root <pasta>] [--update] [--limit N]` | Importa o dump SQL do MariaDB (aplicações, catálogo, períodos, pagamentos/boletos, triagens, reuniões, eventos, anexos e comprovantes). Use `--update` para reimportar sem duplicar; sem `--storage-root`, os arquivos são ignorados com aviso. Guia completo em `docs/IMPORTACAO_DADOS_LEGADOS.md`. |

#### simulate_journey — usuários criados

O comando cria (se não existirem) usuários com credenciais conhecidas:

- `sim_candidate` (candidato), `sim_teacher` (docente), `sim_secretariat` (secretaria) — senha `sim-senha-123`.

#### simulate_journey — flags principais

| Flag | Ação |
|---|---|
| `--modality project\|consultation` | Modalidade (padrão: `project`). |
| `--submit` | Cria a inscrição (taxa de inscrição gerada → `awaiting_payment`). |
| `--pay [--method pix\|boleto\|manual]` | Paga **todas** as taxas pendentes (inscrição, projeto, complementar). |
| `--submit-dataset [--channel file\|external_link]` | Projeto: envia dados para auditoria. |
| `--review approved\|needs_correction\|rejected` | Revisa a submissão de auditoria. |
| `--resolve convert_to_consultation\|reject_application\|transfer_term` | Resolve uma rejeição de auditoria. |
| `--schedule-screening` / `--screening-decision approved_as_project\|approved_as_consultation\|not_approved` | Agenda e decide a triagem (Projeto). |
| `--schedule-consultation` / `--consultation-decision approved_as_project\|approved_as_consultation\|not_approved` | Agenda e decide a reunião (Consulta). |
| `--refund` | Cria, aprova e executa um reembolso do valor pago. |
| `--step N` | Executa apenas a etapa N da sequência canônica da modalidade. |
| `--all` | Executa a jornada completa até o estado final (para na 1ª falha). |
| `--status` / `--protocol <protocolo>` | Imprime o estado atual da inscrição mais recente (ou a do `--protocol`). |
| `--json` | Emite uma linha JSON final (protocolo, estado e período), consumida pelos fixtures E2E. |

Exemplos:

```bash
docker compose exec web python manage.py simulate_journey --all --modality project --method pix
docker compose exec web python manage.py simulate_journey --all --modality consultation --method boleto
docker compose exec web python manage.py simulate_journey --modality project --submit --pay --submit-dataset --review rejected --resolve reject_application
docker compose exec web python manage.py simulate_journey --step 4
docker compose exec web python manage.py simulate_journey --protocol 123456789 --status
```

#### simulate_journey — notas operacionais

- **Sem rede externa:** os gateways de Pix (REST) e Boleto (SOAP) são mockados internamente; a confirmação Pix passa pelo caminho real do webhook. Nenhum teste/criação de dados deve depender de conectividade externa.
- **Boleto exige `DEBUG=True`** (guard do `simulate_payment`). Em testes, usar `override_settings(DEBUG=True)`. Alternativas sem DEBUG: `--method pix` ou `--method manual`.
- **Storage de mídia:** o comando isola `MEDIA_ROOT` em diretório temporário porque o bind mount `/app` pertence ao usuário do host (uid 1001) e o container roda como `appuser` (uid 1000). Uploads reais (Pix QR, anexos, boletos) exigem o diretório `media/` gravável — isso vale para o app inteiro, não só para a simulação.
- **Uma inscrição por invocação:** ao encadear várias flags numa única chamada, cada flag executa uma vez (argparse deduplica flags repetidas, ex.: `--pay`). Para continuar em outra etapa, repita o comando informando `--protocol` ou deixe alvo padrão na inscrição mais recente.
- **Testes do comando:** `apps/applications/tests/test_simulate_journey_command.py` cobre as jornadas Projeto/Consulta, rejeição, conversão, `--step` e reembolso.

### 4.2 Importação de dump legado (SQL + storage)

Guia completo: `docs/IMPORTACAO_DADOS_LEGADOS.md`.

Pontos críticos:

- O legado tem projeto e banco em servidores separados, mas ambos são do mesmo projeto.
- O storage dos anexos é o root do disco `local` do Laravel, **não** necessariamente `storage/app`. Descubra no legado com:
  `php -r "require 'vendor/autoload.php'; \$app=require 'bootstrap/app.php'; \$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap(); print_r(config('filesystems.disks'));"`
  Neste projeto, o root do `local` é `/storage/inscricoes-cea/app`.
- Gere dump e archive a partir de `$HOME` no servidor legado; não deixe arquivos no diretório do projeto em produção.
- O archive do storage deve conter `app/<protocolo>/<arquivo>`. Monte-o read-only e rode:
  `docker compose run --rm -v /home/<usuario>/cea-legacy-storage-local:/legacy-storage:ro web python manage.py import_legacy_sql --dump /app/tmp/<dump>.sql --storage-root /legacy-storage/app --update`
- `--update` é idempotente; sem ele, a segunda execução falha com “protocolo duplicado” (`TS-IMP-007`).
- Sem `--storage-root`, anexos e comprovantes são ignorados com aviso.
- Dump e storage contêm dados pessoais: manter fora do Git (`$HOME` ou `tmp/`) e nunca commitar.

---

## 5. Regras de Ouro da Implementação

Para manter a base de código limpa, coesa e alinhada à arquitetura aprovada, você **deve** seguir estas regras:

1. **Views Finas, Serviços Gordos:** Nunca coloque lógica financeira, orquestração de Pix/Boleto ou cálculos de taxa diretamente na View. A View apenas recebe os dados, chama o Serviço de Domínio (ex: `PaymentOrchestrationService`), e retorna a resposta.
2. **Respeite os Estados:** A máquina de estados da inscrição (`lifecycle_status`) e dos pagamentos (`payment_state`) é estrita. Não invente novos status. Utilize exatamente os listados em `DATABASE_SCHEMA.md`.
3. **Não Apague Registros:** O sistema requer retenção total. Implemente exclusão lógica via `soft_deleted_at`. Nunca utilize o comando `DELETE` do SQL ou `model.delete()` de forma física, exceto em casos de contorno ou falhas isoladas de transação explícita.
4. **Tratamento de Valores Financeiros:** Sempre utilize tipos decimais (`DECIMAL(10,2)`) para manipular moedas. Evite falhas de arredondamento usando as bibliotecas apropriadas da linguagem para precisão monetária (ex: módulo `decimal` no Python).
5. **Idempotência em Webhooks:** Se você for implementar o endpoint de webhook do Pix, assegure-se de que o código pode processar o mesmo payload múltiplas vezes sem duplicar o pagamento.
6. **Gerenciamento de Arquivos:** Nunca salve arquivos diretamente no banco. Grave em *storage* privado e armazene apenas os metadados (como `sha256_checksum` e tamanho) na tabela `file_assets`.

---

## 6. Plano de Execução (Roadmap de Implementação)

Agentes devem focar em entregas incrementais. Não tente implementar o sistema inteiro em um único prompt. Siga a ordem abaixo ao construir o projeto:

### Fase 1: Setup e Infraestrutura Base
- Inicializar o projeto na linguagem/framework escolhido (padrão recomendado: Python/Django).
- Configurar banco de dados relacional (MySQL/MariaDB).
- Criar o modelo base de Usuário (`users`) sobrescrevendo o padrão do framework.
- Configurar autenticação local e preparar *stubs* para OAuth (Senha Única USP).

### Fase 2: Modelagem Inicial (Core)
- Implementar as tabelas sem dependências ou com poucas dependências: `academic_terms`, `catalog_options`.
- Implementar `service_applications` (Inscrições) e `application_catalog_selections`.
- Implementar `file_assets` e `application_attachments`.

### Fase 3: Domínio de Auditoria
- Criar a modelagem de `dataset_audit_submissions`, `dataset_audit_reviews` e `dataset_audit_resolutions`.
- Implementar o `DatasetAuditService` contendo a lógica de transição (aprovação, pedido de correção e rejeição).

### Fase 4: Módulo Financeiro
- Implementar tabelas de `fee_requirements` e `payment_instruments`.
- Criar *mock/stubs* para os gateways externos de Pix e Boleto.
- Codificar o `PaymentOrchestrationService` (Garantir a regra: apenas UM instrumento ativo por taxa).
- Codificar as conciliações e pagamentos manuais.

### Fase 5: Domínio de Agendamento e Notificações
- Implementar tabelas e regras para triagens (`project_screenings`) e reuniões (`consultation_meetings`).
- Construir o serviço de notificações (disparo de e-mails) utilizando fila assíncrona.

### Fase 6: Resgate e Migração
- Implementar `legacy_ownership_claims`.
- Implementar fluxo seguro de resgate por token via e-mail.

---

## 7. Padrões de Testes exigidos do Agente

Ao gerar código de testes, você deve:

- Traduzir explicitamente os cenários de `TEST_SCENARIOS.md` para código.
- Nomear os testes fazendo referência ao ID do cenário. Exemplo: `def test_TS_PAY_005_apenas_um_instrumento_ativo_por_taxa(self):`.
- **Convenção de IDs:** o documento usa hífen (`TS-NOT-001`); o teste Python usa underscore
  (`test_TS_NOT_001_...`). Todo ID citado no nome do teste deve existir em `docs/TEST_SCENARIOS.md`
  (verificado pelo meta-teste em `apps/base/tests.py`).
- Em testes de notificação, afirmar também **destinatário** (candidato vs.
  `settings.NOTIFICATION_CENTER_EMAIL`) e **BCC** quando o fluxo usar cópia oculta.
- Usar _Mocks_ e _Patching_ para chamadas externas (Pix via API Rest, Boleto via SOAP). **Nenhum teste gerado deve depender de conectividade de rede externa**.
- Verificar efeitos colaterais: certifique-se de que o teste valide não apenas o retorno da API/Serviço, mas também o registro de auditoria em `application_events`.

---

## 8. Resolução de Conflitos ou Ambiguidade

Se, durante a geração do código, você encontrar ambiguidade entre os documentos:
1. Privilegie o **DATABASE_SCHEMA.md** para decisões sobre tipos de dados, limites e chaves, pois é a verdade absoluta do armazenamento.
2. Privilegie a **ARCHITECTURE.md** para decisões sobre onde colocar a lógica (qual serviço/classe criar).
3. Privilegie o **TEST_SCENARIOS.md** para definir os critérios de aceite se o comportamento não estiver claro no schema.
4. Caso a lógica de negócio exija uma suposição, pare e insira um comentário no formato `// TODO(AI-Assumption): <descrição>` ou solicite esclarecimento ao desenvolvedor humano que está revisando suas saídas.
