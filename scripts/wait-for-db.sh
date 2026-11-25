#!/usr/bin/env bash
# Espera o banco EXTERNO por domínio, com retry e timeout.
#
# - Lê DATABASE_URL ou DB_CONNECTION/DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD.
# - Rejeita DB_HOST que seja nome de serviço Compose (db, mysql, postgres...)
#   salvo quando DB_ALLOW_LOCAL_HOST=true (apenas stacks de teste).
# - Não imprime senha nem connection string completa.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/db-env.sh
source "${SCRIPT_DIR}/lib/db-env.sh"

db_env_load
db_assert_external_host

TIMEOUT="${DB_WAIT_TIMEOUT:-90}"
INTERVAL="${DB_WAIT_INTERVAL:-3}"

echo "[wait-for-db] Aguardando banco em ${DB_HOST}:${DB_PORT} (timeout ${TIMEOUT}s)..."

deadline=$((SECONDS + TIMEOUT))
until db_tcp_check; do
    if [ "$SECONDS" -ge "$deadline" ]; then
        echo "[wait-for-db] ERRO: banco ${DB_HOST}:${DB_PORT} não respondeu em ${TIMEOUT}s." >&2
        echo "[wait-for-db] Verifique o DNS do banco no ambiente e as credenciais da stack." >&2
        exit 1
    fi
    sleep "$INTERVAL"
done

echo "[wait-for-db] Banco acessível em ${DB_HOST}:${DB_PORT}."
