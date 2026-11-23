# Python USP Starter Kit 🇧🇷

**A base oficial para desenvolvimento web e ciência de dados na Universidade de São Paulo.**

## 1. Visão Geral

O **Python USP Starter Kit** é a tradução da excelência do ecossistema *Laravel USP* para o mundo Python. Criado para atender à crescente demanda por aplicações de Inteligência Artificial e Análise de Dados na universidade, este kit oferece uma estrutura "batteries-included" que elimina semanas de configuração inicial.

Diferente de um projeto Django comum, ele já nasce integrado à infraestrutura corporativa da USP (Senha Única e Base Replicada), seguindo rigorosamente os padrões de segurança da STI e as melhores práticas de Engenharia de Software (Twelve-Factor App).

**Por que usar este kit?**
*   🚀 **Zero Config:** Autenticação OAuth e conexões de banco legados (Sybase) pré-configuradas.
*   🤖 **AI-Ready:** Estrutura otimizada para desenvolvimento com Agentes Autônomos (Google Antigravity/Cursor).
*   🔒 **Seguro por Padrão:** Containerização *hardened* e gestão segura de segredos.

---

## 2. Principais Funcionalidades

*   **Autenticação Híbrida:**
    *   Backend primário via **Senha Única USP (OAuth 1.0a)** utilizando `senhaunica-socialite-python`.
    *   Sistema de permissões (Admin/Manager/User) integrado ao Django Admin.
    *   *Login-as* (impersonate) para suporte e debug.
*   **Integração com Replicado:**
    *   Camada de dados híbrida: **SQLAlchemy 2.0** para consultas de alta performance no Sybase/MSSQL e **Django ORM** para dados locais.
    *   Models pré-mapeados para tabelas comuns (Pessoa, Graduação, Pós).
*   **Infraestrutura de Background:**
    *   **Redis** pronto para cache/filas, incluído como serviço no `docker-compose.yml`. (A integração com Celery fica como etapa de configuração posterior.)
*   **Monitoramento e Logs:**
    *   Logging estruturado pronto para ingestão (Graylog/Elastic).
    *   Auditoria automática de ações de usuários.

---

## 3. Guia de Instalação

### Pré-requisitos
*   Docker & Docker Compose
*   (Opcional) Poetry 1.8+ — necessário apenas para rodar lint/testes localmente; o deploy via Docker instala as dependências dentro do contêiner.

### Passo a Passo

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/ime-usp-br/python-usp-starter-kit.git meu-projeto
    cd meu-projeto
    ```

2.  **Configure as Variáveis de Ambiente:**
    Crie o arquivo de configuração a partir do modelo antes de iniciar os contêineres:
    ```bash
    cp .env.example .env
    ```
    > ⚠️ **Nota:** Lembre-se de abrir o arquivo `.env` recém-criado e preencher as variáveis necessárias (senhas, chaves e credenciais) — em especial `SENHAUNICA_KEY`, `SENHAUNICA_SECRET`, `SENHAUNICA_CALLBACK_ID` e o bloco `REPLICADO_*` — antes de prosseguir.

3.  **Suba a infraestrutura:**
    ```bash
    # Constroi a imagem e inicia Banco (Postgres), Redis e a Aplicação Web
    docker compose up -d --build
    ```
    O `entrypoint` (`scripts/entrypoint.sh`) aplica as **migrações** e o `collectstatic` automaticamente a cada subida do contêiner `web`, então não é preciso executá-los manualmente.

4.  **(Opcional) Reaplique migrações manualmente:**
    ```bash
    # Use apenas se precisar reaplicar migrações fora do boot do contêiner:
    docker compose exec web python manage.py migrate
    ```

Acesse em: `http://localhost:8000`

---

## 4. Configuração do Ambiente (.env)

Abaixo estão as variáveis críticas presentes no seu arquivo `.env` que conectam sua aplicação ao ecossistema da USP.

| Categoria | Variável | Descrição |
| :--- | :--- | :--- |
| **Geral** | `DJANGO_ENV` | `development` ou `production`. |
| | `SECRET_KEY` | Chave criptográfica do Django. |
| | `DEBUG` | `True`/`False` (modo debug do Django). |
| | `ALLOWED_HOSTS` | Hosts permitidos, separados por vírgula (ex: `localhost,127.0.0.1`). |
| | `WEB_PORT` | Porta exposta no host pelo `web` (padrão `8000`). |
| **Senha Única** | `SENHAUNICA_KEY` | *Consumer Key* fornecida pela STI. |
| | `SENHAUNICA_SECRET` | *Consumer Secret* fornecida pela STI. |
| | `SENHAUNICA_CALLBACK_ID` | ID de callback registrado junto à STI. Obrigatório. A URL de callback é montada automaticamente a partir da rota `/callback/`. |
| | `SENHAUNICA_ENV` | Endpoints da USP: `prod` (padrão) ou `dev` (homologação). |
| | `SENHAUNICA_OAUTH_BASE_URL` | Opcional: sobrescreve a base OAuth (ex.: `http://senhaunica-faker:3141/wsusuario/oauth`). Vazio usa a URL oficial. |
| **Replicado** | `REPLICADO_HOST` | Host/IP do servidor da réplica local. |
| | `REPLICADO_PORT` | Porta do servidor: `1433` (MSSQL, padrão) ou `5000` (Sybase legado). |
| | `REPLICADO_DATABASE` | Nome do banco (ex: `replicado`). |
| | `REPLICADO_USERNAME` | Usuário de leitura. |
| | `REPLICADO_PASSWORD` | Senha do banco. |
| | `REPLICADO_SYBASE` | `1` (ou `True`) apenas para compatibilidade com drivers legados Sybase. Deixe em branco para MSSQL puro. |

---

## 5. Desenvolvimento Agent-First (Google Antigravity)

Este projeto adota a filosofia **Agent-First**. Se você utiliza o **Google Antigravity IDE** ou editores baseados em IA, o diretório `.agent/` funciona como o "Mission Control".

### Regras para Agentes (`.agent/rules`)
O arquivo `.agent/rules/python_usp.md` contém diretrizes estritas que garantem que o código gerado por IA siga nossos padrões.

*   **Regra de Ouro:** Agentes nunca devem usar SQL puro sem `sqlalchemy.text()` e *bind parameters*.
*   **Tipagem:** Todo código novo deve passar na validação estrita do `mypy`.
*   **Padrão de Camadas:** A lógica de negócio deve residir em `services/`, nunca nas `views`.

**Exemplo de Prompt para o Agente:**
> "Utilizando as regras do projeto, crie um Service que busque o histórico escolar de um aluno no Replicado e salve um resumo em cache Redis."

---

## 6. Segurança (SSDLC)

A segurança não é opcional na USP. O kit implementa:

1.  **Docker Hardening:**
    *   Usuário não-root (`appuser`) no container de produção.
    *   Imagem base `python:3.14-slim-bookworm` para reduzir superfície de ataque.
2.  **Proteção Web:**
    *   Middlewares de segurança do Django ativados (`SECURE_SSL_REDIRECT`, `CSRF_COOKIE_SECURE` em prod).
    *   Sanitização automática de inputs do Replicado para evitar *SQL Injection* em bancos legados.
3.  **Gestão de Segredos:**
    *   O `docker-compose.yml` nunca expõe portas de banco de dados para a rede externa em produção.

---

## 7. Testes e Qualidade

Mantemos a qualidade do código alta para garantir a manutenibilidade a longo prazo.

**Rodar Testes Unitários e de Integração:**
```bash
# Roda a suíte completa com relatório de cobertura
poetry run pytest --cov=apps
```

**Verificação de Estilo e Tipagem (Linting):**
```bash
# Verifica PEP 8 e bugs potenciais
poetry run ruff check .

# Verifica consistência de tipos
poetry run mypy .
```

**Testes E2E de navegador (Playwright em stack isolada):**

`docker-compose.e2e.yml` sobe uma stack descartável (banco próprio, app Django
e container Playwright). A suíte não depende da stack de DEV nem de rede
externa:

- Pix e Boleto usam **gateways simulados em memória** (`PAYMENT_GATEWAY_FAKE=True`);
- o webhook Pix é exercitado por POST na própria aplicação;
- a Senha Única usa o **`uspdev/senhaunica-faker`** (OAuth1 fake, sem USP real);
- Celery roda em modo eager e os e-mails vão para uma **caixa em arquivo**, lida
  pelos testes (cadastro/confirmação e recuperação de senha);
- ao final, a stack e o banco são removidos (`down -v`).

```bash
# Sobe a stack isolada, roda toda a suíte e derruba tudo ao final
./scripts/run_e2e.sh

# Rodar apenas um arquivo/teste:
./scripts/run_e2e.sh -q e2e/test_full_journeys_e2e.py
./scripts/run_e2e.sh -k reembolso

# Rodar o subconjunto crítico (mesmo do PR):
./scripts/run_e2e.sh -m p0

# Manter a stack de pé para depuração (logs, Playwright trace etc.)
E2E_KEEP_STACK=1 ./scripts/run_e2e.sh
```

**Isolamento dos testes**

Cada teste cria seu próprio candidato e seu próprio período no namespace
`9000–9999`. O período é enviado explicitamente pelo campo oculto do formulário,
então a suíte não depende de “período mais recente” nem da ordem dos testes.
Todas as jornadas criam e avançam a inscrição pela UI; `simulate_journey` fica
restrito aos testes de comando. Ao final, inscrições são soft-deletadas,
usuários criados são desativados e o namespace E2E é limpo com
`e2e_cleanup --purge-e2e-terms` (exclusivo da stack descartável).

**CI**

- Pull request: job `P0`, com limite de 7 minutos para a execução do pytest.
- Nightly/manual: suíte completa, com limite de 20 minutos.
- Artefatos de falha: JUnit, trace e screenshot em `e2e-artifacts/` e
  `test-results/`.
- O workflow está em `.github/workflows/e2e.yml` e roda o pytest no host do
  runner, usando `docker-compose.e2e.host.yml` apenas para publicar as portas
  em loopback (sem socket Docker dentro do container E2E).