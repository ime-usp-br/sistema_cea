#!/usr/bin/env bash
# Executa os testes E2E de navegador (Playwright) em um container dedicado,
# contra a aplicação Django em execução (padrão: http://cea.dev.ime).
#
# Pré-requisitos:
#   - Stack da aplicação de pé: `docker compose up -d`
#   - Docker com `host-gateway` (Docker 20.10+)
#
# Variáveis:
#   E2E_BASE_URL   URL da aplicação (padrão: http://cea.dev.ime)
#   E2E_ARGS       argumentos extras do pytest (ou passe via "$@")
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

BASE_URL="${E2E_BASE_URL:-http://cea.dev.ime}"

echo "==> Garantindo aplicação de pé em ${BASE_URL}"
curl -sf -o /dev/null "${BASE_URL}/" || {
    echo "A aplicação não responde em ${BASE_URL}." >&2
    echo "Suba a stack (docker compose up -d) e verifique o reverse proxy." >&2
    exit 1
}

echo "==> Rodando testes E2E no container (Playwright + Chromium)"
# O fixture ``seed_database`` executa o seed pelo serviço ``web`` do próprio
# compose E2E e o cleanup marca as inscrições criadas ao final da sessão.
docker compose -f docker-compose.e2e.yml run --rm --build \
    -e E2E_BASE_URL="${BASE_URL}" \
    -e E2E_HOST_ROOT="${ROOT}" \
    e2e \
    pytest -q -p no:cacheprovider e2e -c e2e/pytest.ini ${E2E_ARGS:-} "$@"
