from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    import httpx


class PixGatewayError(RuntimeError):
    """Erro de comunicação com o gateway Pix."""


class PixGateway:
    """Cliente HTTP para o serviço externo de cobrança Pix (WSPIX).

    Contrato WSPIX (docs/PIX.md e tmp/extracted/pix_spec.txt):

    - base [dev]: ``https://api-dev.portalservicos.usp.br/wspix/api``
    - autenticação: headers ``X-Username``/``X-Password``
    - endpoints sob ``<URL_BASE>/pix``: ``gerar``, ``<idfpix>``,
      ``listarConcluidos``, ``<idfpix>/pdf``, ``<idfpix>/qrcode``,
      ``<idfpix>/simularPag`` (somente dev) e ``webhookConfig``.

    A integração é feita via API REST/JSON usando ``httpx``. O transporte é
    criado de forma lazy dentro de cada método para que o módulo possa ser
    importado mesmo quando ``httpx`` não está disponível no ambiente (os
    testes simulam completamente essas chamadas).
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.PIX_BASE_URL).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "X-Username": settings.PIX_USERNAME,
            "X-Password": settings.PIX_PASSWORD,
        }

    def _url(self, *parts: str) -> str:
        return "/".join([self.base_url, *parts])

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        import httpx

        try:
            with httpx.Client(timeout=30) as client:
                response = client.request(
                    method,
                    self._url(path),
                    json=json_body,
                    params=params,
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text[:1000]
            except Exception:  # noqa: BLE001 - corpo é diagnóstico opcional
                body = ""
            detail = f"{exc}"
            if body:
                detail = f"{detail}. Resposta do gateway: {body}"
            raise PixGatewayError(
                f"Falha na requisição {method} {path}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise PixGatewayError(
                f"Falha na requisição {method} {path}: {exc}"
            ) from exc

    def generate_pix(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /pix/gerar — gera uma cobrança Pix.

        Retorna ``idfpix``, ``qrCode`` (copia-e-cola) e ``qrCodeImgBase64``.
        """
        response = self._request("POST", "pix/gerar", json_body=payload)
        return response.json()

    def check_pix_status(self, idfpix: str, *, verify: bool = False) -> dict[str, Any]:
        """GET /pix/<idfpix> — consulta o status de uma cobrança.

        Quando ``verify`` é True é enviado o queryParam ``verificar``: o
        gateway verifica o pagamento no banco, realiza a baixa em caso de
        falha de webhook e re-dispara o webhook cadastrado.
        """
        params: dict[str, Any] = {"verificar": "1"} if verify else {}
        response = self._request("GET", f"pix/{idfpix}", params=params)
        return response.json()

    def list_completed_pix(self, dtaini: str, dtafim: str) -> list[dict[str, Any]]:
        """GET /pix/listarConcluidos — lista Pix pagos em um período.

        Contrato WSPIX: os parâmetros ``dtaini`` e ``dtafim`` no formato
        ``dd/MM/aaaa hh:mm:ss`` e o período não pode exceder 30 dias.
        """
        response = self._request(
            "GET",
            "pix/listarConcluidos",
            params={"dtaini": dtaini, "dtafim": dtafim},
        )
        return response.json()

    def generate_pdf(self, idfpix: str) -> bytes:
        """GET /pix/<idfpix>/pdf — baixa o PDF com os dados e o QR Code."""
        response = self._request("GET", f"pix/{idfpix}/pdf")
        return response.content

    def generate_qrcode(self, idfpix: str) -> bytes:
        """GET /pix/<idfpix>/qrcode — baixa a imagem do QR Code."""
        response = self._request("GET", f"pix/{idfpix}/qrcode")
        return response.content

    def simulate_payment(self, idfpix: str) -> dict[str, Any]:
        """PATCH /pix/<idfpix>/simularPag — simula o pagamento (somente dev)."""
        response = self._request("PATCH", f"pix/{idfpix}/simularPag")
        return response.json()

    def configure_webhook(self, url: str, token: str) -> dict[str, Any]:
        """POST /pix/webhookConfig — cadastra a URL de webhook da aplicação."""
        response = self._request(
            "POST",
            "pix/webhookConfig",
            json_body={"url": url, "token": token},
        )
        return response.json()

    def remove_webhook(self) -> dict[str, Any]:
        """DELETE /pix/webhookConfig — remove o webhook cadastrado."""
        response = self._request("DELETE", "pix/webhookConfig")
        return response.json()
