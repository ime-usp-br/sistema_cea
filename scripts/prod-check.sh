#!/usr/bin/env bash
# Valida que a stack de deploy NÃO contém anti-padrões de infraestrutura.
#
# Verifica o docker-compose.yml normalizado (`docker compose config`):
#   - nenhum serviço de banco;
#   - nenhuma rede `db`;
#   - nenhuma porta publicada (`ports:`);
#   - nenhum bind mount de código;
#   - nenhum env_file obrigatório;
#   - DB_HOST configurado como domínio, não como serviço Compose.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
FAIL=0

fail() {
    echo "FALHA: $*" >&2
    FAIL=1
}

config="$(docker compose -f "$COMPOSE_FILE" config)"

services="$(docker compose -f "$COMPOSE_FILE" config --services)"
for forbidden in db mysql mariadb postgres postgresql; do
    if printf '%s\n' "$services" | grep -qx "$forbidden"; then
        fail "serviço de banco '${forbidden}' presente na stack de deploy."
    fi
done

if printf '%s\n' "$config" | grep -Eq '^[[:space:]]+ports:'; then
    fail "a stack de deploy publica portas (use expose)."
fi

if printf '%s\n' "$config" | grep -q 'type: bind'; then
    fail "a stack de deploy usa bind mount."
fi

if printf '%s\n' "$config" | grep -Eq '^[[:space:]]+env_file:'; then
    fail "a stack de deploy usa env_file (as variáveis vêm do Portainer)."
fi

if printf '%s\n' "$config" | grep -Eq '^[[:space:]]+db:'; then
    fail "rede 'db' presente na stack de deploy."
fi

if grep -Eq '^name:' "$COMPOSE_FILE"; then
    fail "docker-compose.yml tem 'name' hardcoded (use o nome da stack no Portainer)."
fi

db_host="${DB_HOST:-}"
if [ -z "$db_host" ]; then
    echo "AVISO: DB_HOST não está definido no ambiente desta validação." >&2
else
    case "${db_host,,}" in
        db | mysql | postgres | postgresql | mariadb | localhost | 127.0.0.1 | 0.0.0.0 | redis)
            fail "DB_HOST='${db_host}' não é um domínio externo."
            ;;
    esac
fi

if grep -Eq '^\s*-\s*\.:/|^\s*-\s*\.\/:/' "$COMPOSE_FILE"; then
    fail "bind mount de código-fonte no docker-compose.yml."
fi

if [ "$FAIL" -ne 0 ]; then
    echo "prod-check: FALHOU." >&2
    exit 1
fi

echo "prod-check: OK — sem banco, sem rede db, sem portas, sem bind mount e sem env_file."
