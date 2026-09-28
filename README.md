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

**Testes E2E de navegador (Playwright em container):**

Sobe um container dedicado (com Chromium) que roda a suíte `e2e/` contra a
aplicação já em execução. O script semeia os usuários/período via
`seed_e2e` e depois roda o pytest no container.

```bash
# A aplicação deve estar de pé (docker compose up -d)
./scripts/run_e2e.sh

# Rodar apenas um teste/arquivo:
./scripts/run_e2e.sh test_journeys_e2e.py -k pagar_taxa

# Apontar para outra URL:
E2E_BASE_URL=http://cea.local ./scripts/run_e2e.sh
```

O alvo padrão é `http://cea.dev.ime` (configurável por `E2E_BASE_URL`). O
container e2e resolve os domínios de desenvolvimento pelo host
(`extra_hosts: host-gateway` em `docker-compose.e2e.yml`).