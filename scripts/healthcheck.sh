#!/usr/bin/env bash
# Healthcheck da aplicação (executado dentro do container pela stack e por
# `make health`). Usa o endpoint real de login, que exige o processo web vivo.
set -euo pipefail

PORT="${WEB_PORT:-8000}"
URL="${HEALTHCHECK_URL:-http://127.0.0.1:${PORT}/auth/login/}"

# ALLOWED_HOSTS restritivo rejeitaria "Host: 127.0.0.1". Usa o primeiro host
# público configurado (ou HEALTHCHECK_HOST) no header, mantendo a conexão local.
HOST_HEADER="${HEALTHCHECK_HOST:-}"
if [ -z "$HOST_HEADER" ] && [ -n "${ALLOWED_HOSTS:-}" ]; then
    IFS=',' read -r FIRST_HOST _ <<<"$ALLOWED_HOSTS"
    FIRST_HOST="$(echo "$FIRST_HOST" | tr -d '[:space:]')"
    if [ -n "$FIRST_HOST" ] && [ "$FIRST_HOST" != "*" ]; then
        HOST_HEADER="$FIRST_HOST"
    fi
fi

CURL_ARGS=(-fsS --max-time 5 --output /dev/null)
if [ -n "$HOST_HEADER" ]; then
    CURL_ARGS+=(-H "Host: ${HOST_HEADER}")
fi

if command -v curl >/dev/null 2>&1; then
    curl "${CURL_ARGS[@]}" "$URL"
else
    python - "$URL" "$HOST_HEADER" <<'PY' >/dev/null
import sys
import urllib.request

url, host_header = sys.argv[1], sys.argv[2]
headers = {'Host': host_header} if host_header else {}
request = urllib.request.Request(url, headers=headers)
urllib.request.urlopen(request, timeout=5)
PY
fi

echo "[healthcheck] OK: ${URL} (Host: ${HOST_HEADER:-127.0.0.1})"
