#!/usr/bin/env bash
# Executa os testes E2E de navegador (Playwright) contra a aplicação Django
# em execução no container (http://localhost:8000).
#
# Pré-requisitos:
#   - Container web de pé: `docker compose up -d`
#   - Python 3 no host (o venv e o Chromium do Playwright são criados sob /tmp).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${E2E_VENV:-/tmp/kilo-e2e-venv}"

echo "==> Garantindo aplicação de pé em http://cea.local"
curl -sf -o /dev/null http://cea.local/ || { echo "A aplicação não responde em cea.local. Verifique o reverse proxy (npm) e o container."; exit 1; }

echo "==> Preparando venv em ${VENV}"
if [ ! -x "${VENV}/bin/pytest" ]; then
    python3 -m venv "${VENV}"
    "${VENV}/bin/pip" install --quiet --upgrade pip
    "${VENV}/bin/pip" install --quiet pytest pytest-playwright
    "${VENV}/bin/python" -m playwright install chromium
fi

echo "==> Rodando testes E2E"
cd "${ROOT}"
"${VENV}/bin/pytest" e2e -c e2e/pytest.ini --browser chromium \
    -o addopts="" \
    "$@"
