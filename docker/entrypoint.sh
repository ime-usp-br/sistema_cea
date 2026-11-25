#!/bin/bash
# Entrypoint único da stack de aplicação (dev, homologação e produção).
#
# Responsabilidades:
#   - esperar o banco externo por DOMÍNIO (nunca por serviço Compose);
#   - aplicar migrações somente no papel web e quando RUN_MIGRATIONS=true;
#   - rodar seeders somente quando RUN_SEEDERS=true e nunca em produção;
#   - aquecer estáticos/cache quando WARM_CACHE=true (ou DEBUG=False);
#   - iniciar Gunicorn ou o servidor de desenvolvimento conforme DJANGO_ENV;
#   - iniciar Celery quando CONTAINER_ROLE=worker (sem migrações/seeders).
#
# Qualquer comando explícito passado ao container continua tendo prioridade
# (usado por `docker compose run ... -- <comando>` e pela suíte de testes).
set -euo pipefail

log() {
    echo "[entrypoint] $*"
}

die() {
    echo "[entrypoint] ERRO: $*" >&2
    exit 1
}

if [ "$#" -gt 0 ]; then
    log "Executando comando explícito: $*"
    exec "$@"
fi

CONTAINER_ROLE="${CONTAINER_ROLE:-web}"
APP_ENV="${APP_ENV:-dev}"
DJANGO_ENV="${DJANGO_ENV:-}"
if [ -z "$DJANGO_ENV" ]; then
    case "$APP_ENV" in
        homolog | prod) DJANGO_ENV="production" ;;
        *) DJANGO_ENV="development" ;;
    esac
fi
WEB_PORT="${WEB_PORT:-8000}"

case "${CONTAINER_ROLE}" in
    web | worker | beat) ;;
    *) die "CONTAINER_ROLE inválido: '${CONTAINER_ROLE}' (use web, worker ou beat)." ;;
esac

log "Papel: ${CONTAINER_ROLE}; DJANGO_ENV=${DJANGO_ENV}; APP_ENV=${APP_ENV:-dev}"

# Espera o banco externo por domínio. O script falha com mensagem clara em
# timeout e rejeita hosts que sejam nomes de serviço Compose.
/app/scripts/wait-for-db.sh

if [ "${CONTAINER_ROLE}" = "worker" ] || [ "${CONTAINER_ROLE}" = "beat" ]; then
    # O worker usa a mesma imagem e as mesmas variáveis, mas NÃO roda
    # migrações nem seeders (evita concorrência entre réplicas).
    if [ "${CONTAINER_ROLE}" = "beat" ]; then
        log "Iniciando Celery beat..."
        exec celery -A core beat -l "${CELERY_LOG_LEVEL:-info}"
    fi
    log "Iniciando Celery worker..."
    exec celery -A core worker -l "${CELERY_LOG_LEVEL:-info}"
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    log "Aplicando migrações do banco..."
    python manage.py migrate --noinput
else
    log "RUN_MIGRATIONS=false: migrações não serão aplicadas."
fi

# collectstatic é idempotente e necessário em todos os modos (WhiteNoise serve
# o STATIC_ROOT mesmo em DEBUG, pois usamos whitenoise.runserver_nostatic).
log "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

if [ "${WARM_CACHE:-false}" = "true" ]; then
    log "Aquecendo cache (WARM_CACHE=true)..."
    if ! python manage.py shell -c "from django.core.cache import cache; cache.get_or_set('cea:boot-warmup', 1, 60)"; then
        log "AVISO: falha ao aquecer o cache; seguindo (rate limit é fail-open)."
    fi
fi

if [ "${RUN_SEEDERS:-false}" = "true" ]; then
    if [ "${APP_ENV:-dev}" = "prod" ]; then
        die "RUN_SEEDERS=true é proibido com APP_ENV=prod."
    fi
    log "Executando seed de demonstração (RUN_SEEDERS=true)..."
    python manage.py seed_demo
fi

if [ "${DJANGO_ENV}" = "production" ]; then
    log "Iniciando Gunicorn em 0.0.0.0:${WEB_PORT}..."
    exec gunicorn core.wsgi:application \
        --bind "0.0.0.0:${WEB_PORT}" \
        --workers "${GUNICORN_WORKERS:-3}" \
        --access-logfile - \
        --error-logfile -
fi

log "Iniciando servidor de desenvolvimento Django (runserver)..."
exec python manage.py runserver "0.0.0.0:${WEB_PORT}"
