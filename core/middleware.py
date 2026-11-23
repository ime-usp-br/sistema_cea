"""Rate limiting por rota (D-03).

Perfis (janela de 60s por padrão, configurável por env):

- login: 5/min por IP + username submetido;
- webhook Pix: 60/min por IP;
- downloads/PDF: 30/min por usuário autenticado (ou IP);
- demais POSTs: 20/min por usuário autenticado (ou IP).

O contador vive no cache Redis. Em caso de indisponibilidade do cache, a
requisição é liberada (fail-open) e o erro é registrado, para não derrubar a
aplicação inteira por causa do limitador.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)

DOWNLOAD_MARKERS = ("/pdf/", "/arquivo/", "/anexo/", "/comprovante/", "/qrcode/")
EXEMPT_PREFIXES = ("/admin/", "/static/", "/media/", "/favicon.ico")


@dataclass(frozen=True)
class RateLimitRule:
    scope: str
    limit: int
    window: int


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:48]


def _client_ip(request: HttpRequest) -> str:
    if getattr(settings, "RATE_LIMIT_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "unknown"


def _user_identifier(request: HttpRequest) -> str:
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"
    return f"ip:{_client_ip(request)}"


def _login_identifier(request: HttpRequest) -> str:
    username = ""
    try:
        username = request.POST.get("username", "")
    except Exception:  # pragma: no cover - POST malformado não deve derrubar o middleware
        username = ""
    return _hash_identifier(
        f"{_client_ip(request)}:{username.strip().lower()}"
    )


def _classify(request: HttpRequest) -> tuple[RateLimitRule, str] | None:
    if not getattr(settings, "RATE_LIMIT_ENABLED", True):
        return None

    path = request.path
    if path.startswith(EXEMPT_PREFIXES):
        return None

    window = int(getattr(settings, "RATE_LIMIT_WINDOW", 60))
    normalized = path.rstrip("/")

    if request.method == "POST" and normalized == "/auth/login":
        return (
            RateLimitRule(
                "login",
                int(getattr(settings, "RATE_LIMIT_LOGIN", 5)),
                window,
            ),
            _login_identifier(request),
        )

    if request.method == "POST" and normalized == "/webhooks/pix":
        return (
            RateLimitRule(
                "webhook",
                int(getattr(settings, "RATE_LIMIT_WEBHOOK", 60)),
                window,
            ),
            f"ip:{_client_ip(request)}",
        )

    if request.method == "GET" and any(marker in path for marker in DOWNLOAD_MARKERS):
        return (
            RateLimitRule(
                "download",
                int(getattr(settings, "RATE_LIMIT_DOWNLOAD", 30)),
                window,
            ),
            _user_identifier(request),
        )

    if request.method == "POST":
        return (
            RateLimitRule(
                "post",
                int(getattr(settings, "RATE_LIMIT_POST", 20)),
                window,
            ),
            _user_identifier(request),
        )

    return None


def _increment(rule: RateLimitRule, identifier: str) -> int:
    key = f"ratelimit:{rule.scope}:{identifier}"
    cache.add(key, 0, timeout=rule.window)
    try:
        return int(cache.incr(key))
    except ValueError:
        # A chave expirou entre o add e o incr; recomeça a janela.
        cache.set(key, 1, timeout=rule.window)
        return 1


class RateLimitMiddleware:
    """Aplica os perfis de limite antes de chegar à view."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        classified = _classify(request)
        if classified is None:
            return self.get_response(request)

        rule, identifier = classified
        if rule.limit <= 0:
            return self.get_response(request)

        try:
            count = _increment(rule, identifier)
        except Exception:
            logger.exception("Falha ao aplicar rate limit; liberando requisição.")
            return self.get_response(request)

        remaining = max(0, rule.limit - count)
        if count > rule.limit:
            response: HttpResponse = JsonResponse(
                {
                    "error": "rate_limited",
                    "detail": "Muitas tentativas. Tente novamente em instantes.",
                },
                status=429,
            )
            response["Retry-After"] = str(rule.window)
            response["X-RateLimit-Limit"] = str(rule.limit)
            response["X-RateLimit-Remaining"] = "0"
            return response

        response = self.get_response(request)
        response["X-RateLimit-Limit"] = str(rule.limit)
        response["X-RateLimit-Remaining"] = str(remaining)
        return response
