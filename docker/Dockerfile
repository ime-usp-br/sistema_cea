# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder: instala dependências em um virtualenv isolado.
# Nenhuma ferramenta de build vai para a imagem final.
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv \
    && pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock ./

# Somente dependências de runtime na imagem de produção.
RUN poetry install --no-interaction --no-ansi --no-root --only main

# ---------------------------------------------------------------------------
# Builder de testes: mesmo virtualenv + grupo dev (pytest, ruff, mypy...).
# Usado apenas pelo alvo `test`, nunca pela imagem de deploy.
# ---------------------------------------------------------------------------
FROM builder AS builder-dev

RUN poetry install --no-interaction --no-ansi --no-root --with dev

# ---------------------------------------------------------------------------
# Runtime: dependências de SO de runtime, código e usuário não-root.
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:/app/apps" \
    PATH="/opt/venv/bin:$PATH" \
    TZ=America/Sao_Paulo

# Bibliotecas de runtime do WeasyPrint (PDF), cliente do Postgres (backup e
# restore) e curl (healthcheck). Sem compiladores nem headers -dev.
#
# O cliente do Postgres vem do repositório PGDG na MESMA major do servidor
# (17), pois pg_dump/psql de versão anterior recusam servidores mais novos.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    tzdata \
    libpq5 \
    libffi8 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libharfbuzz-subset0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    fonts-dejavu \
    fonts-urw-base35 \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 appgroup \
    && useradd -u 1000 -g appgroup -m -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN mkdir -p staticfiles media backups \
    && chmod +x docker/entrypoint.sh scripts/*.sh \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]

# ---------------------------------------------------------------------------
# Alvo de testes: imagem de runtime + dependências de desenvolvimento.
# `docker compose -f docker-compose.test.yml build --build-arg` usa target=test.
# ---------------------------------------------------------------------------
FROM runtime AS test

USER root

COPY --from=builder-dev /opt/venv /opt/venv
COPY . .

RUN chmod +x docker/entrypoint.sh scripts/*.sh \
    && chown -R appuser:appgroup /app

USER appuser

ENTRYPOINT ["/app/docker/entrypoint.sh"]
