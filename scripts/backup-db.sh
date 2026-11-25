#!/usr/bin/env bash
# Backup padronizado do banco do projeto (externo, por domínio).
#
# - Suporta PostgreSQL (pg_dump) e MySQL/MariaDB (mysqldump) via DB_CONNECTION.
# - Gera <PROJECT_NAME>-<APP_ENV>-<DB_NAME>-YYYYmmdd-HHMMSS.sql.gz + .sha256.
# - Aplica retenção por BACKUP_RETENTION_DAYS.
# - A senha vai por variável de ambiente (PGPASSWORD/MYSQL_PWD), nunca por argv.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/db-env.sh
source "${SCRIPT_DIR}/lib/db-env.sh"

db_env_load
db_assert_external_host

PROJECT_NAME="${PROJECT_NAME:-sistema-cea}"
APP_ENV="${APP_ENV:-dev}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

case "$(db_family)" in
    postgres)
        command -v pg_dump >/dev/null 2>&1 || db_env_die "pg_dump não encontrado."
        command -v psql >/dev/null 2>&1 || db_env_die "psql não encontrado."
        ;;
    mysql)
        command -v mysqldump >/dev/null 2>&1 || db_env_die "mysqldump não encontrado."
        command -v mysql >/dev/null 2>&1 || db_env_die "mysql não encontrado."
        ;;
esac

mkdir -p "$BACKUP_DIR"

echo "[backup-db] Validando conexão com ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
if ! db_check_connection; then
    db_env_die "não foi possível conectar ao banco ${DB_NAME} em ${DB_HOST}:${DB_PORT}."
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BASENAME="${PROJECT_NAME}-${APP_ENV}-${DB_NAME}-${TIMESTAMP}"
TARGET="${BACKUP_DIR%/}/${BASENAME}.sql.gz"
TMP="${TARGET}.tmp"

cleanup_tmp() {
    rm -f "$TMP"
}
trap cleanup_tmp EXIT

echo "[backup-db] Gerando backup em ${TARGET}..."

case "$(db_family)" in
    postgres)
        if ! PGPASSWORD="$DB_PASSWORD" pg_dump \
            --no-owner --no-privileges --clean --if-exists --format=plain \
            --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" \
            --dbname "$DB_NAME" | gzip -9 >"$TMP"; then
            db_env_die "pg_dump falhou."
        fi
        ;;
    mysql)
        if ! MYSQL_PWD="$DB_PASSWORD" mysqldump \
            --single-transaction --quick --no-tablespaces \
            --host "$DB_HOST" --port "$DB_PORT" --user "$DB_USER" \
            --databases "$DB_NAME" | gzip -9 >"$TMP"; then
            db_env_die "mysqldump falhou."
        fi
        ;;
esac

mv "$TMP" "$TARGET"
trap - EXIT

if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$TARGET" >"${TARGET}.sha256"
else
    shasum -a 256 "$TARGET" >"${TARGET}.sha256"
fi

echo "[backup-db] Backup concluído: ${TARGET}"
echo "[backup-db] Checksum: ${TARGET}.sha256"

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [ "$RETENTION_DAYS" -gt 0 ]; then
    echo "[backup-db] Aplicando retenção de ${RETENTION_DAYS} dia(s)..."
    find "$BACKUP_DIR" -type f \
        -name "${PROJECT_NAME}-${APP_ENV}-${DB_NAME}-*.sql.gz" \
        -mtime +"$RETENTION_DAYS" -print -delete || true
    find "$BACKUP_DIR" -type f \
        -name "${PROJECT_NAME}-${APP_ENV}-${DB_NAME}-*.sql.gz.sha256" \
        -mtime +"$RETENTION_DAYS" -print -delete || true
else
    echo "[backup-db] Retenção desativada (BACKUP_RETENTION_DAYS=${RETENTION_DAYS})."
fi
