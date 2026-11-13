# Container isolado para rodar a suíte E2E de navegador (Playwright).
#
# Além do Python/pytest/Chromium, inclui o CLI do Docker e o plugin do Compose
# para que os fixtures possam executar `docker compose -f docker-compose.e2e.yml
# run web manage.py ...` (seed, `simulate_journey` e cleanup) através do socket
# do host montado em runtime.
#
# Build:
#   docker compose -f docker-compose.e2e.yml build
# Uso (recomendado): ./scripts/run_e2e.sh
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Docker CLI + Compose plugin (usa o daemon do host via socket montado).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg libatomic1 \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Dependências de teste + navegadores do Playwright.
RUN pip install --no-cache-dir pytest 'pytest-playwright>=0.6' \
    && python -m playwright install --with-deps chromium

# O código-fonte é montado em /workspace em runtime (ver docker-compose.e2e.yml).
WORKDIR /workspace

CMD ["pytest", "-q", "-p", "no:cacheprovider", "e2e", "-c", "e2e/pytest.ini"]
