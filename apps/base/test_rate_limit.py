"""Testes de D-03: perfis de rate limiting e resposta 429."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import User

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "rate-limit-tests",
    }
}


class RateLimitTests(TestCase):
    def setUp(self) -> None:
        self._rate_settings = override_settings(
            CACHES=LOCMEM_CACHE,
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_WINDOW=60,
            RATE_LIMIT_LOGIN=2,
            RATE_LIMIT_WEBHOOK=1,
            RATE_LIMIT_DOWNLOAD=1,
            RATE_LIMIT_POST=2,
        )
        self._rate_settings.enable()
        self.addCleanup(self._rate_settings.disable)
        cache.clear()

    def _login(self, username: str = "naoexiste") -> Any:
        return self.client.post(
            reverse("login"),
            {"username": username, "password": "senha-errada"},
            REMOTE_ADDR="198.51.100.10",
        )

    # TST-BASE-001
    def test_login_limita_por_ip_e_username(self) -> None:
        first = self._login("alvo")
        second = self._login("alvo")
        blocked = self._login("alvo")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.headers["Retry-After"], "60")
        self.assertEqual(blocked.headers["X-RateLimit-Limit"], "2")
        self.assertEqual(blocked.headers["X-RateLimit-Remaining"], "0")
        self.assertIn("Muitas tentativas", blocked.json()["detail"])

        # Outro username no mesmo IP tem balde próprio.
        self.assertEqual(self._login("outro").status_code, 200)

    # TST-BASE-002
    def test_login_headers_de_limite_em_resposta_permitida(self) -> None:
        response = self._login("alvo")
        self.assertEqual(response.headers["X-RateLimit-Limit"], "2")
        self.assertEqual(response.headers["X-RateLimit-Remaining"], "1")

    @override_settings(RATE_LIMIT_WEBHOOK=1)
    # TST-BASE-003
    def test_webhook_limita_por_ip(self) -> None:
        payload = json.dumps({"idfpix": "x", "status": "Pago"})
        first = self.client.post(
            reverse("pix:webhook"),
            data=payload,
            content_type="application/json",
            REMOTE_ADDR="198.51.100.11",
        )
        second = self.client.post(
            reverse("pix:webhook"),
            data=payload,
            content_type="application/json",
            REMOTE_ADDR="198.51.100.11",
        )
        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)

    # TST-BASE-004
    def test_post_limita_por_usuario(self) -> None:
        user = User.objects.create_user(
            username="rate-post", email="rate-post@example.com", password="x"
        )
        self.client.force_login(user)
        first = self.client.post("/inscricoes/nova/", data={})
        second = self.client.post("/inscricoes/nova/", data={})
        blocked = self.client.post("/inscricoes/nova/", data={})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(blocked.status_code, 429)

    # TST-BASE-005
    def test_download_limita_por_usuario(self) -> None:
        user = User.objects.create_user(
            username="rate-download", email="rate-download@example.com", password="x"
        )
        self.client.force_login(user)
        path = "/inscricoes/000000000/pdf/ficha/"
        self.assertNotEqual(self.client.get(path).status_code, 429)
        self.assertEqual(self.client.get(path).status_code, 429)

    @override_settings(RATE_LIMIT_ENABLED=False)
    # TST-BASE-006
    def test_limite_desabilitado_nao_bloqueia(self) -> None:
        for _ in range(6):
            response = self._login("alvo")
        self.assertEqual(response.status_code, 200)

    @override_settings(RATE_LIMIT_LOGIN=2)
    # TST-BASE-007
    def test_falha_do_cache_libera_requisicao(self) -> None:
        with patch("core.middleware._increment", side_effect=RuntimeError("cache down")):
            response = self._login("alvo")
        self.assertEqual(response.status_code, 200)

    @override_settings(RATE_LIMIT_LOGIN=1, RATE_LIMIT_TRUST_X_FORWARDED_FOR=True)
    # TST-BASE-008
    def test_login_usa_x_forwarded_for_quando_configurado(self) -> None:
        first = self.client.post(
            reverse("login"),
            {"username": "alvo", "password": "senha-errada"},
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1",
        )
        blocked = self.client.post(
            reverse("login"),
            {"username": "alvo", "password": "senha-errada"},
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1",
        )
        outro_ip = self.client.post(
            reverse("login"),
            {"username": "alvo", "password": "senha-errada"},
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="203.0.113.2",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(outro_ip.status_code, 200)

    @override_settings(DEBUG=True)
    # TST-BASE-009
    def test_e2e_clear_cache_limpa_contadores(self) -> None:
        cache.set("ratelimit:login:teste", 3, timeout=60)
        call_command("e2e_clear_cache")
        self.assertIsNone(cache.get("ratelimit:login:teste"))

    # TST-BASE-013
    def test_reset_de_senha_e_resgate_respeitam_rate_limit_post(self) -> None:
        cache.clear()
        for _ in range(2):
            response = self.client.post(
                reverse("password_reset"), {"email": "alvo@example.com"}
            )
            self.assertNotEqual(response.status_code, 429)
        blocked = self.client.post(
            reverse("password_reset"), {"email": "alvo@example.com"}
        )
        self.assertEqual(blocked.status_code, 429)

        cache.clear()
        user = User.objects.create_user(
            username="rate-claim", email="rate-claim@example.com", password="x"
        )
        self.client.force_login(user)
        for _ in range(2):
            response = self.client.post(reverse("imports:claim_request"), {})
            self.assertNotEqual(response.status_code, 429)
        blocked = self.client.post(reverse("imports:claim_request"), {})
        self.assertEqual(blocked.status_code, 429)
