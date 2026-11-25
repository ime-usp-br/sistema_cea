#!/usr/bin/env bash
# Utilitários compartilhados pelos scripts de banco.
# Não imprime senha, token nem a connection string completa.

db_env_die() {
    echo "ERRO: $*" >&2
    exit 1
}

_db_url_decode() {
    local value="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))' "$value"
        return
    fi
    printf '%s' "$value"
}

# Preenche DB_CONNECTION, DB_HOST, DB_PORT, DB_NAME, DB_USER e DB_PASSWORD.
# Precedência: DATABASE_URL (quando não vazia) > variáveis DB_*.
db_env_load() {
    local url="${DATABASE_URL:-}"

    if [ -n "${url//[[:space:]]/}" ]; then
        local rest scheme creds hostpart hostport
        scheme="${url%%://*}"
        rest="${url#*://}"

        if [[ "$rest" == *"@"* ]]; then
            creds="${rest%%@*}"
            hostpart="${rest#*@}"
            DB_USER="${creds%%:*}"
            if [[ "$creds" == *":"* ]]; then
                DB_PASSWORD="${creds#*:}"
            else
                DB_PASSWORD=""
            fi
            DB_USER="$(_db_url_decode "$DB_USER")"
            DB_PASSWORD="$(_db_url_decode "$DB_PASSWORD")"
        else
            hostpart="$rest"
        fi

        hostport="${hostpart%%/*}"
        DB_NAME="${hostpart#*/}"
        DB_NAME="${DB_NAME%%\?*}"
        DB_HOST="${hostport%%:*}"
        if [[ "$hostport" == *":"* ]]; then
            DB_PORT="${hostport##*:}"
        else
            DB_PORT=""
        fi
        DB_CONNECTION="$scheme"
    fi

    DB_CONNECTION="${DB_CONNECTION:-postgres}"
    DB_HOST="${DB_HOST:-}"
    DB_PORT="${DB_PORT:-}"
    DB_NAME="${DB_NAME:-}"
    DB_USER="${DB_USER:-}"
    DB_PASSWORD="${DB_PASSWORD:-}"

    local family
    family="$(db_family)"
    if [ -z "$DB_PORT" ]; then
        if [ "$family" = "postgres" ]; then
            DB_PORT="5432"
        else
            DB_PORT="3306"
        fi
    fi

    [ -n "$DB_HOST" ] || db_env_die "DB_HOST não definido (use o domínio do banco externo)."
    [ -n "$DB_NAME" ] || db_env_die "DB_NAME não definido."
    [ -n "$DB_USER" ] || db_env_die "DB_USER não definido."
}

db_family() {
    case "${DB_CONNECTION,,}" in
        postgres | postgresql | pgsql) echo "postgres" ;;
        mysql | mariadb) echo "mysql" ;;
        *)
            db_env_die "DB_CONNECTION '${DB_CONNECTION}' não suportado (use postgres ou mysql)."
            ;;
    esac
}

db_assert_external_host() {
    if [ "${DB_ALLOW_LOCAL_HOST:-false}" = "true" ]; then
        return 0
    fi
    case "${DB_HOST,,}" in
        db | mysql | postgres | postgresql | mariadb | localhost | 127.0.0.1 | 0.0.0.0 | redis)
            db_env_die \
                "DB_HOST='${DB_HOST}' não é um domínio de banco externo. Use db-<env>.<dominio> (ou defina DB_ALLOW_LOCAL_HOST=true apenas em testes)."
            ;;
    esac
}

db_tcp_check() {
    timeout 3 bash -c 'exec 3<>"/dev/tcp/$0/$1"' "$DB_HOST" "$DB_PORT" 2>/dev/null
}

db_check_connection() {
    case "$(db_family)" in
        postgres)
            PGPASSWORD="$DB_PASSWORD" psql \
                --no-psqlrc --no-password --quiet \
                --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" \
                --dbname "$DB_NAME" --command 'SELECT 1' >/dev/null
            ;;
        mysql)
            MYSQL_PWD="$DB_PASSWORD" mysql \
                --connect-timeout=10 \
                --host "$DB_HOST" --port "$DB_PORT" --user "$DB_USER" \
                --database "$DB_NAME" --execute 'SELECT 1' >/dev/null
            ;;
    esac
}
