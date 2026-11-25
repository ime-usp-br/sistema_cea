#!/usr/bin/env bash
# Restore padronizado de um backup .sql.gz do banco do projeto.
#
# Uso: scripts/restore-db.sh <arquivo.sql.gz> [--confirm-prod]
#
# - Valida existência, extensão e checksum (.sha256) quando disponível.
# - Exige confirmação explícita (ou RESTORE_CONFIRM=yes para automação).
# - Em APP_ENV=prod exige também --confirm-prod.
# - NÃO apaga o backup após o restore.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/db-env.sh
source "${SCRIPT_DIR}/lib/db-env.sh"

CONFIRM_PROD=false
BACKUP_FILE=""

for arg in "$@"; do
    case "$arg" in
        --confirm-prod) CONFIRM_PROD=true ;;
        -*) db_env_die "opção desconhecida: ${arg}" ;;
        *)
            [ -z "$BACKUP_FILE" ] || db_env_die "informe apenas um arquivo de backup."
            BACKUP_FILE="$arg"
            ;;
    esac
done

[ -n "$BACKUP_FILE" ] || db_env_die "uso: $0 <arquivo.sql.gz> [--confirm-prod]"
[ -f "$BACKUP_FILE" ] || db_env_die "arquivo não encontrado: ${BACKUP_FILE}"

case "$BACKUP_FILE" in
    *.sql.gz | *.sql) ;;
    *) db_env_die "extensão inválida (esperado .sql.gz ou .sql): ${BACKUP_FILE}" ;;
esac

db_env_load
db_assert_external_host

APP_ENV="${APP_ENV:-dev}"

if [ -f "${BACKUP_FILE}.sha256" ]; then
    echo "[restore-db] Validando checksum..."
    expected="$(awk '{print $1}' "${BACKUP_FILE}.sha256")"
    if command -v sha256sum >/dev/null 2>&1; then
        actual="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"
    else
        actual="$(shasum -a 256 "$BACKUP_FILE" | awk '{print $1}')"
    fi
    [ -n "$expected" ] && [ "$expected" = "$actual" ] \
        || db_env_die "checksum não confere para ${BACKUP_FILE}."
    echo "[restore-db] Checksum OK."
else
    echo "[restore-db] Aviso: checksum ${BACKUP_FILE}.sha256 não encontrado; seguindo sem validação."
fi

if [ "$APP_ENV" = "prod" ] && [ "$CONFIRM_PROD" != "true" ]; then
    db_env_die "APP_ENV=prod exige a flag --confirm-prod para restore."
fi

echo "[restore-db] ATENÇÃO: operação DESTRUTIVA."
echo "[restore-db] Alvo: ${DB_HOST}:${DB_PORT}/${DB_NAME} (${DB_CONNECTION}, APP_ENV=${APP_ENV})"
echo "[restore-db] Arquivo: ${BACKUP_FILE}"

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
    read -r -p "[restore-db] Digite 'restore' para confirmar: " answer
    [ "$answer" = "restore" ] || db_env_die "restore cancelado."
fi

case "$(db_family)" in
    postgres)
        command -v psql >/dev/null 2>&1 || db_env_die "psql não encontrado."
        ;;
    mysql)
        command -v mysql >/dev/null 2>&1 || db_env_die "mysql não encontrado."
        ;;
esac

echo "[restore-db] Validando conexão..."
if ! db_check_connection; then
    db_env_die "não foi possível conectar ao banco ${DB_NAME} em ${DB_HOST}:${DB_PORT}."
fi

if [[ "$BACKUP_FILE" == *.gz ]]; then
    DECOMPRESS=(gzip -dc "$BACKUP_FILE")
else
    DECOMPRESS=(cat "$BACKUP_FILE")
fi

echo "[restore-db] Restaurando..."
case "$(db_family)" in
    postgres)
        "${DECOMPRESS[@]}" | PGPASSWORD="$DB_PASSWORD" psql \
            --no-psqlrc --no-password --quiet \
            --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" \
            --dbname "$DB_NAME" --set ON_ERROR_STOP=1
        ;;
    mysql)
        "${DECOMPRESS[@]}" | MYSQL_PWD="$DB_PASSWORD" mysql \
            --host "$DB_HOST" --port "$DB_PORT" --user "$DB_USER" \
            --database "$DB_NAME"
        ;;
esac

echo "[restore-db] Restore concluído. O backup original foi preservado."
