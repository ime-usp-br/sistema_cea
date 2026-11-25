"""Integração Senha Única com endpoints configuráveis (inclusive faker E2E).

O pacote ``senhaunica-socialite-python`` fixa as URLs oficiais de dev/prod.
Esta camada cria o cliente a partir das configurações do projeto e permite
sobrescrever a base OAuth (usada pelo ``uspdev/senhaunica-faker`` na stack
E2E), sem alterar o comportamento de produção quando o override está vazio.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from senhaunica_socialite.client import SenhaUnicaClient

logger = logging.getLogger(__name__)


def get_senhaunica_client(request: HttpRequest) -> SenhaUnicaClient | None:
    """Cria o cliente OAuth1 com as configurações do projeto."""
    if not settings.SENHAUNICA_KEY or not settings.SENHAUNICA_SECRET:
        return None
    callback = request.build_absolute_uri(reverse("users:senhaunica_callback"))
    client = SenhaUnicaClient(
        settings.SENHAUNICA_KEY,
        settings.SENHAUNICA_SECRET,
        callback,
        callback_id=settings.SENHAUNICA_CALLBACK_ID or None,
        env=settings.SENHAUNICA_ENV,
    )
    base = (settings.SENHAUNICA_OAUTH_BASE_URL or "").strip().rstrip("/")
    if base:
        client.authorize_url = f"{base}/authorize"
        client.request_token_url = f"{base}/request_token"
        client.access_token_url = f"{base}/access_token"
        client.user_info_url = f"{base}/usuariousp"
    return client


def senhaunica_login(request: HttpRequest) -> HttpResponse:
    """Inicia o handshake OAuth1 e redireciona para a autorização externa."""
    client = get_senhaunica_client(request)
    if client is None:
        return HttpResponse("Senha Única não configurada.", status=503)
    try:
        token_response = client.fetch_request_token()
        oauth_token = token_response.get("oauth_token")
        oauth_token_secret = token_response.get("oauth_token_secret")
        if not oauth_token or not oauth_token_secret:
            return HttpResponse(
                "Falha ao obter o token de autorização da Senha Única.",
                status=502,
            )
        request.session["senhaunica_token_secret"] = oauth_token_secret
        return redirect(client.get_authorization_url(oauth_token))
    except Exception:  # noqa: BLE001 - falha externa vira 502 controlado
        logger.exception("Falha ao iniciar o login pela Senha Única.")
        return HttpResponse("Falha ao iniciar o login pela Senha Única.", status=502)


def senhaunica_callback(request: HttpRequest) -> HttpResponse:
    """Conclui o handshake OAuth1 e autentica o usuário."""
    oauth_verifier = request.GET.get("oauth_verifier")
    oauth_token = request.GET.get("oauth_token")
    oauth_token_secret = request.session.get("senhaunica_token_secret")
    if not oauth_verifier or not oauth_token or not oauth_token_secret:
        return HttpResponse(
            "Callback inválido ou sessão expirada.", status=400
        )

    request.session.pop("senhaunica_token_secret", None)
    user: Any = authenticate(
        request,
        oauth_token=oauth_token,
        oauth_token_secret=oauth_token_secret,
        oauth_verifier=oauth_verifier,
    )
    if user is None:
        return HttpResponse("Falha na autenticação pela Senha Única.", status=403)
    login(request, user)
    return redirect(settings.SENHAUNICA_LOGIN_REDIRECT_URL or "/")
