# Deploy — Inscrições CEA

Padrão único de deploy para **dev**, **homologação** e **produção** com
Docker Compose v2 + Portainer + Nginx Proxy Manager (NPM).

A aplicação é a mesma nos três ambientes. Só mudam as variáveis configuradas
na stack do Portainer.

---

## 1. Arquitetura

```
Internet
  │  HTTPS (TLS no NPM)
  ▼
Nginx Proxy Manager (rede Docker externa `web`)
  │  http://sistema-cea-<APP_ENV>-web:${WEB_PORT}
  ▼
Stack `sistema-cea-<env>` (Portainer)
  ├─ web    (Gunicorn/runserver, rede default + web)
  ├─ worker (Celery, rede default)
  └─ redis  (broker/cache interno, rede default)
       │
       └── DB_HOST: db-<env>.<dominio>:<DB_PORT>  (banco EXTERNO, fora do Docker da app)
```

- O banco **não pertence** a esta stack nem a este repositório.
- O banco é acessado por **domínio** (`DB_HOST`), nunca por serviço Compose.
- A aplicação **não publica portas**. O NPM alcança o container pelo alias
  estável `sistema-cea-<APP_ENV>-web` na rede `web`.
- O Redis é broker/cache interno da stack (não é banco de dados) e não é exposto.
- Logs vão para stdout/stderr; healthcheck no endpoint real `/auth/login/`.

### Por que `web` também está na rede `default`

O serviço `web` participa da rede `default` do projeto apenas para falar com o
`redis` interno, e da rede externa `web` para o NPM. Não há rede `db`, alias de
banco nem acesso do banco à rede `web`.

---

## 2. Ambientes

| Ambiente | Branch alvo | Stack Portainer | Banco (domínio) | Proxy Host NPM | Domínio público |
|---|---|---|---|---|---|
| dev | `main` (branch atual) | `sistema-cea-dev` | `db-dev.<dominio>` | `dev.<dominio>` | `https://dev.<dominio>` |
| homologação | `main` (branch atual) | `sistema-cea-homolog` | `db-homolog.<dominio>` | `homolog.<dominio>` | `https://homolog.<dominio>` |
| produção | `main` (branch atual) | `sistema-cea-prod` | `db.<dominio>` | `<dominio>` | `https://<dominio>` |

- Branch alvo: **`main`** (branch estável do repositório).
- Não existe documento de mapeamento de branches; branches diferentes de
  `main` são temporárias.
- Domínios reais de banco/NPM/produção: **não identificados** neste repositório.
  Substitua `<dominio>` pelo domínio institucional do ambiente.
- Produção atual: **não identificada** neste repositório. Se houver uma
  produção temporária em outra branch/infra, ela **não** é alterada por este
  padrão; o cutover é planejado no relatório da execução.

### Valores esperados por ambiente

| Variável | dev | homologação | produção |
|---|---|---|---|
| `APP_ENV` | `dev` | `homolog` | `prod` |
| `DJANGO_ENV` | `development` | `production` | `production` |
| `DEBUG` | `true` | `false` | `false` |
| `DB_HOST` | `db-dev.<dominio>` | `db-homolog.<dominio>` | `db.<dominio>` |
| `RUN_MIGRATIONS` | `true` | `true` | `true` |
| `RUN_SEEDERS` | `true` | `false` | `false` |
| `WARM_CACHE` | `false` | `true` | `true` |
| `PAYMENT_GATEWAY_FAKE` | `false` | `false` | `false` |

Mapeamento da variável nativa do Django:

- `APP_ENV=dev` → `DJANGO_ENV=development`, `DEBUG=true`;
- `APP_ENV=homolog` → `DJANGO_ENV=production`, `DEBUG=false`;
- `APP_ENV=prod` → `DJANGO_ENV=production`, `DEBUG=false` (o app recusa subir
  com `DEBUG=true` ou `DJANGO_ENV≠production` em `APP_ENV=prod`).

---

## 3. Variáveis

Contrato completo e copiável: [`.env.example`](../../.env.example).
Todas as chaves existem em todos os ambientes; apenas os valores mudam.

| Variável | Obrigatória | dev | homologação | produção | Secreta | Observações |
|---|---|---|---|---|---|---|
| `APP_ENV` | sim | `dev` | `homolog` | `prod` | não | Rótulo de ambiente/scripts |
| `DJANGO_ENV` | não | `development` | `production` | `production` | não | Nativo do Django |
| `DEBUG` | sim | `true` | `false` | `false` | não | Proibido `true` em prod |
| `SECRET_KEY` | sim | valor local | valor do ambiente | valor do ambiente | **sim** | Gerar por ambiente |
| `ALLOWED_HOSTS` | sim | `dev.<dominio>` | `homolog.<dominio>` | `<dominio>` | não | Sem esquema |
| `APP_URL` | não | `https://dev.<dominio>` | `https://homolog.<dominio>` | `https://<dominio>` | não | URL pública |
| `TZ` | não | `America/Sao_Paulo` | idem | idem | não | Fuso |
| `WEB_PORT` | não | `8000` | `8000` | `8000` | não | Porta interna |
| `DB_CONNECTION` | não | `postgres` | `postgres` | `postgres` | não | `postgres`/`mysql` |
| `DB_HOST` | sim | `db-dev.<dominio>` | `db-homolog.<dominio>` | `db.<dominio>` | não | **Domínio**, não serviço |
| `DB_PORT` | não | `5432` | `5432` | `5432` | não | Porta do banco |
| `DB_NAME` | sim | nome do projeto | idem | idem | não | Específico do projeto |
| `DB_USER` | sim | usuário do projeto | idem | idem | não | Solicitar à infra |
| `DB_PASSWORD` | sim | senha do ambiente | senha do ambiente | senha do ambiente | **sim** | Portainer |
| `DATABASE_URL` | não | vazio | vazio | vazio | **sim** | Opcional; prefira `DB_*` |
| `RUN_MIGRATIONS` | não | `true` | `true` | `true` | não | Só no serviço web |
| `RUN_SEEDERS` | não | `true` | `false` | `false` | não | Proibido em prod |
| `WARM_CACHE` | não | `false` | `true` | `true` | não | Aquece cache/estáticos |
| `CONTAINER_ROLE` | não | `web` | `web` | `web` | não | `worker` é definido pelo compose |
| `REDIS_URL` | não | `redis://redis:6379/0` | idem | idem | não | Redis interno |
| `BACKUP_DIR` | não | `/app/backups` | idem | idem | não | Volume persistente |
| `BACKUP_RETENTION_DAYS` | não | `7` | `7` | `7` | não | Retenção local |
| `CSRF_TRUSTED_ORIGINS` | não | `https://dev.<dominio>` | `https://homolog.<dominio>` | `https://<dominio>` | não | Obrigatório atrás de HTTPS |
| `SECURE_PROXY_SSL_HEADER` | não | `HTTP_X_FORWARDED_PROTO,https` | idem | idem | não | Confia no NPM |
| `SENHAUNICA_*` | depende | credenciais dev | credenciais homolog | credenciais prod | **sim** | OAuth USP |
| `PIX_*` / `BANK_SLIP_*` | depende | dev | homolog | prod | **sim** | Gateways |
| `MAIL_*` | depende | `MAIL_DRIVER=log` | SMTP real | SMTP real | **sim** | Notificações |
| `PAYMENT_GATEWAY_FAKE` | não | `false` | `false` | `false` | não | Só teste |

Segredos ficam no Portainer por enquanto. A estrutura permite migrar para um
secret manager no futuro sem renomear variáveis.

### Como trocar segredos no futuro

1. Gere o novo valor fora do repositório (ex.: `python -c "import secrets;
   print(secrets.token_urlsafe(64))"`).
2. Atualize a variável no campo *Environment variables* da stack no Portainer.
3. Faça redeploy da stack (o Portainer recria os containers com o novo valor).
4. Valide login, e-mails e integrações afetadas; acompanhe os logs.
5. Revogue o segredo antigo no provedor (SMTP, WSSPIX, Senha Única etc.).
6. Para migrar a um secret manager: crie os secrets com os **mesmos nomes** e
   troque a origem no deploy, sem alterar o restante do contrato.

---

## 4. Checklist do Portainer

1. Criar a rede externa `web` (se ainda não existir):
   `docker network create web`
2. Criar a stack da aplicação apontando para `docker-compose.yml` deste
   repositório (branch `main`).
3. Configurar **todas** as variáveis no campo *Environment variables* da stack
   (não usar `.env` no servidor). Base: `.env.example`.
4. Definir `DB_HOST` com o domínio do banco **daquele ambiente**.
5. Configurar o Proxy Host no NPM (seção 5).
6. Subir a stack e validar o healthcheck (`make health` ou
   `docker inspect --format '{{.State.Health.Status}}' <container>`).
7. Rodar/confirmar migrações (`RUN_MIGRATIONS=true` no boot ou `make migrate`).
8. Smoke test: abrir a URL pública, login e uma rota autenticada.
9. Registrar: nome da stack, ambiente, domínio, branch (`main`), imagem/tag
   (`APP_IMAGE`) e data.

Observações:

- O compose não tem `name` hardcoded; o nome da stack no Portainer é a
  identidade do projeto.
- A stack não contém banco, não publica portas e não usa bind mount de código.

---

## 5. Checklist do NPM

Para cada ambiente, criar um **Proxy Host**:

| Campo | dev | homologação | produção |
|---|---|---|---|
| Domain Names | `dev.<dominio>` | `homolog.<dominio>` | `<dominio>` |
| Scheme | `http` | `http` | `http` |
| Forward Hostname | `sistema-cea-dev-web` | `sistema-cea-homolog-web` | `sistema-cea-prod-web` |
| Forward Port | `${WEB_PORT}` (8000) | `${WEB_PORT}` | `${WEB_PORT}` |
| Block Common Exploits | sim | sim | sim |
| Websockets Support | conforme necessidade | conforme necessidade | conforme necessidade |

- TLS: certificado do ambiente, redirecionar HTTP→HTTPS, HSTS em homolog/prod.
- `client_max_body_size`: compatível com uploads de anexos/PDF (ex.: `20m`,
  ajuste conforme o maior upload aceito).
- Timeouts de proxy compatíveis com geração de PDF/relatórios.
- Headers: o NPM envia `X-Forwarded-*`; a aplicação confia no proxy via
  `SECURE_PROXY_SSL_HEADER` e `CSRF_TRUSTED_ORIGINS`.
- O NPM **não** expõe banco. O banco tem domínio e porta próprios.
- Não aponte o Proxy Host para nome de container instável: use o alias
  `sistema-cea-<env>-web`.
- O NPM não é alterado automaticamente por este repositório; configure pela UI.

---

## 6. Banco externo (responsabilidade da infraestrutura)

Em cada ambiente existe uma stack de banco dedicada, compartilhada por todos os
projetos daquele ambiente, gerenciada pela infraestrutura, com domínio próprio
(`db-dev.<dominio>`, `db-homolog.<dominio>`, `db.<dominio>`).

O projeto **não** cria, sobe ou gerencia essa stack. Ele conhece apenas host,
porta, nome do banco, usuário e senha.

### Como solicitar banco/usuário à infra

1. Informe projeto (`sistema-cea`), ambiente e nome desejado do banco/usuário.
2. Peça permissões de leitura/escrita no schema do projeto e permissão para
   `CREATE`/`ALTER` (necessário para migrações).
3. Peça o **domínio DNS** do banco acessível a partir dos containers da
   aplicação, com a porta liberada.
4. Peça que o backup central da infra contemple este banco.
5. Registre o domínio na tabela de ambientes (sem credenciais).

### Validar o DNS do banco dentro do container

```bash
docker compose exec web getent hosts "$DB_HOST"
docker compose exec web /app/scripts/wait-for-db.sh
```

Se o domínio não resolver dentro do container, a infra deve fornecer DNS
interno ou endereço acessível. **Não use `extra_hosts` em produção.**

### Regras

- `DB_HOST` não pode ser `db`, `mysql`, `postgres`, `mariadb`, `localhost` ou
  nome de serviço Compose (o entrypoint recusa em deploy).
- Sem `depends_on` de banco; sem rede `db`; sem alias de banco.
- O banco não usa a rede `web`.

---

## 7. Migrações

- `RUN_MIGRATIONS=true` (padrão) faz o entrypoint do serviço **web** rodar
  `python manage.py migrate --noinput` no boot.
- O **worker** nunca roda migrações.
- Em produção, garanta **uma réplica web** durante o boot ou dispare as
  migrações manualmente antes de escalar:

```bash
make migrate
```

- Rollback de migração é responsabilidade do deploy; mantenha backup antes de
  migrações destrutivas.

---

## 8. Healthcheck

O healthcheck consulta o endpoint real `/auth/login/` dentro do container,
enviando `Host` igual ao primeiro item de `ALLOWED_HOSTS` (para funcionar com
`ALLOWED_HOSTS` restritivo). Use `HEALTHCHECK_HOST` para sobrescrever.

```bash
make health
docker inspect --format '{{json .State.Health}}' sistema-cea-prod-web
```

O entrypoint só inicia o servidor após o banco externo responder em
`DB_HOST:DB_PORT` (retry/timeout configuráveis em `DB_WAIT_TIMEOUT` e
`DB_WAIT_INTERVAL`). Em timeout, o container falha com mensagem clara.

---

## 9. Backup e restore

Scripts: [`scripts/backup-db.sh`](../../scripts/backup-db.sh) e
[`scripts/restore-db.sh`](../../scripts/restore-db.sh).

- Funcionam contra o banco externo por domínio, no host ou dentro do container
  (desde que `pg_dump`/`psql` ou `mysqldump`/`mysql` estejam disponíveis; a
  imagem de runtime inclui `postgresql-client`).
- Senha por `PGPASSWORD`/`MYSQL_PWD`, nunca em argumento de linha de comando.
- Backup: `<PROJECT_NAME>-<APP_ENV>-<DB_NAME>-YYYYmmdd-HHMMSS.sql.gz` +
  `.sha256`, em `BACKUP_DIR` (volume `backups`), com retenção por
  `BACKUP_RETENTION_DAYS`.

```bash
# dentro do container web (volume /app/backups)
make backup-db

# restore (destrutivo; pede confirmação)
make restore-db FILE=backups/sistema-cea-dev-sistema_cea-20260101-030000.sql.gz

# em produção, além da confirmação interativa:
make restore-db FILE=backups/... RESTORE_ARGS=--confirm-prod
# ou RESTORE_CONFIRM=yes scripts/restore-db.sh arquivo.sql.gz --confirm-prod
```

Política e continuidade:

- **Retenção local:** `BACKUP_RETENTION_DAYS` (padrão 7 dias).
- **RPO/RTO:** definidos pela infraestrutura central. O backup do projeto
  **complementa** (e não substitui) o backup central da infra.
- **Teste de restore:** trimestralmente, restore em um banco de homologação
  descartável, valide contagens/consultas críticas e descarte o banco de teste.
- O backup nunca é apagado pelo restore.

> Aviso: `make restore-db` monta o arquivo do host em `/restore` e executa o
> script dentro do container. O arquivo precisa existir no host.

---

## 10. Operação local

```bash
cp .env.example .env          # apenas local; o deploy usa o Portainer
# edite DB_HOST/credenciais do ambiente de dev

make config                   # valida a stack
make prod-check               # anti-padrões (banco/portas/bind mounts)
make up                       # sobe a stack
make health
make logs
make test                     # pytest em stack isolada (banco efêmero)
make test-e2e                 # Playwright em stack descartável
make down
```

Hot reload local (opcional, fora do contrato de deploy):

```bash
make up-local                 # docker-compose.yml + docker-compose.local.yml
```

`docker-compose.local.yml` é o **único** overlay de desenvolvimento com bind
mount de código (porta em loopback). Não é usado no Portainer. O
`docker-compose.e2e.host.yml` também publica portas em loopback, mas apenas para
o CI executar o Playwright no host.

Stacks de teste:

- `docker-compose.test.yml`: pytest de unidade/integração, banco efêmero
  interno, rede isolada, sem portas.
- `docker-compose.e2e.yml` + `docker-compose.e2e.host.yml`: Playwright em stack
  descartável (também com banco efêmero). O override `.host.yml` publica portas
  apenas em loopback para o CI rodar o pytest no host.

---

## 11. Branch e produção

- Branch alvo: **`main`** (branch atual). `main`/`master` é a referência
  estável; demais branches são temporárias.
- Não há `docs/deploy/BRANCHES.md` nem documento vivo de mapeamento.
- Produção canônica = branch `main` nesta stack.
- Produção temporária em outra branch/infra (se existir): **não alterada** por
  este padrão. O cutover (dados, DNS, NPM, segredos, migrações, janela e
  rollback) é registrado apenas no relatório de execução.

---

## 12. Troubleshooting

| Sintoma | Causa provável | Ação |
|---|---|---|
| `DB_HOST não definido` / compose falha com `defina DB_HOST` | variável ausente no Portainer | Preencher no campo *Environment variables* |
| `DB_HOST='db' não é um domínio` | host de serviço Compose | Trocar pelo domínio `db-<env>.<dominio>` |
| `banco ... não respondeu em Ns` | DNS/porta/firewall | Validar `getent hosts`; pedir liberação à infra |
| `502 Bad Gateway` no NPM | alias/rede errados | Confirmar alias `sistema-cea-<env>-web` e rede `web` |
| Healthcheck `unhealthy` | app não iniciou (migração/erro) | `make logs`; verificar migrations/credenciais |
| `CSRF verification failed` | origem HTTPS fora de `CSRF_TRUSTED_ORIGINS` | Ajustar a variável |
| `DEBUG=true` recusado em prod | guard do settings | Definir `DEBUG=false` e `DJANGO_ENV=production` |
| Backup falha com `pg_dump não encontrado` | rodando fora da imagem sem cliente | Rodar via `make backup-db` (container) |
| `prod-check` acusa bind/porta | overlay local aplicado | Usar apenas `docker-compose.yml` |

---

## 13. Legado

O `docs/deploy/_legacy/` guarda o compose antigo que continha o serviço `db` e
o volume `postgres_data` (arquivado, não usado). Não havia
`docker-compose.db.yml` no repositório.

Não crie `docker-compose.db.yml`, serviço `db`, rede `db` nem alias de banco.
