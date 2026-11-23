#!/usr/bin/env bash
# Executa os testes E2E de navegador (Playwright) em uma stack descartável.
#
# A stack (docker-compose.e2e.yml) sobe um banco próprio, o app Django e o
# container Playwright. Pix e Boleto usam gateways simulados em memória, o
# Celery roda em modo eager e os e-mails vão para uma caixa em arquivo — nada
# depende de SMTP, SOAP, webhook ou do gateway Pix da USP.
#
# Variáveis:
#   E2E_ARGS       argumentos extras do pytest (ou passe via "$@")
#   E2E_KEEP_STACK=1  mantém os containers de pé ao final (debug)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-sistema_cea_e2e}"
COMPOSE=(docker compose -p "${PROJECT_NAME}" -f docker-compose.e2e.yml)

cleanup() {
    if [[ "${E2E_KEEP_STACK:-0}" == "1" ]]; then
        echo "==> E2E_KEEP_STACK=1: mantendo a stack ${PROJECT_NAME} de pé"
        return
    fi
    echo "==> Derrubando a stack E2E e o banco descartável"
    "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Subindo a stack E2E isolada (${PROJECT_NAME})"
"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
"${COMPOSE[@]}" up -d --build --wait web db redis senhaunica-faker

echo "==> Executando a suíte E2E (Playwright + Chromium)"
set +e
"${COMPOSE[@]}" run --rm --build \
    -e E2E_BASE_URL="http://web:8000" \
    -e E2E_HOST_ROOT="${ROOT}" \
    -e COMPOSE_PROJECT_NAME="${PROJECT_NAME}" \
    e2e \
    pytest -q -p no:cacheprovider e2e -c e2e/pytest.ini ${E2E_ARGS:-} "$@"
RESULT=$?
set -e

if [[ ${RESULT} -ne 0 ]]; then
    echo "==> Falha nos E2E (código ${RESULT}). Últimos logs do app:"
    "${COMPOSE[@]}" logs --tail=120 web || true
fi
exit ${RESULT}
