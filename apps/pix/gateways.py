from __future__ import annotations

import base64
import uuid
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    import httpx

# PDF mínimo válido (uma página em branco) usado pelo gateway simulado.
_FAKE_PDF = base64.b64decode(
    "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PmVuZG9iagoy"
    "IDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgMS9LaWRzWzMgMCBSXT4+ZW5kYm9iagoz"
    "IDAgb2JqCjw8L1R5cGUvUGFnZS9QYXJlbnQgMiAwIFIvTWVkaWFCb3hbMCAwIDMwMCAx"
    "NTBdPj5lbmRvYmoKeHJlZgowIDQKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5"
    "IDAwMDAwIG4gCjAwMDAwMDAwNTIgMDAwMDAgbiAKMDAwMDAwMDEwMSAwMDAwMCBuIAp0"
    "cmFpbGVyCjw8L1NpemUgNC9Sb290IDEgMCBSPj4Kc3RhcnR4cmVmCjE2NQolJUVPRgo="
)

# PNG 1x1 transparente usado como QR Code simulado.
_FAKE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
_FAKE_PNG_B64 = base64.b64encode(_FAKE_PNG).decode("ascii")


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


class FakePixGateway:
    """Gateway Pix em memória para E2E/dev (sem qualquer chamada de rede).

    O contrato segue docs/PIX.md: ``gerar`` devolve ``idfpix``/``qrCode``/
    ``qrCodeImgBase64``; ``consultar`` devolve os campos documentados e usa o
    status ``Concluído`` para Pix pago (o webhook usa ``Pago``).
    """

    _records: dict[str, dict[str, Any]] = {}

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or "fake://pix"

    @staticmethod
    def _now() -> str:
        from django.utils import timezone

        return timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")

    def generate_pix(self, payload: dict[str, Any]) -> dict[str, Any]:
        reference = f"fp-{uuid.uuid4().hex[:28]}"
        self._records[reference] = {
            "valor": str(payload.get("valor", "0,00")),
            "tipoPessoa": payload.get("tipoPessoa", "PF"),
            "nomePesOrg": payload.get("nomePesOrg", "Pagador E2E"),
            "docPesOrg": payload.get("docPesOrg", "00000000000"),
            "dataGeracao": self._now(),
            "dataExpiracao": self._now(),
        }
        return {
            "idfpix": reference,
            "qrCode": f"00020126580014br.gov.bcb.pix0136{reference}",
            "qrCodeImgBase64": _FAKE_PNG_B64,
        }

    def check_pix_status(self, idfpix: str, *, verify: bool = False) -> dict[str, Any]:
        record = self._records.get(
            idfpix,
            {
                "valor": "0,00",
                "tipoPessoa": "PF",
                "nomePesOrg": "Pagador E2E",
                "docPesOrg": "00000000000",
                "dataGeracao": self._now(),
                "dataExpiracao": self._now(),
            },
        )
        return {
            "idfpix": idfpix,
            "qrCode": f"00020126580014br.gov.bcb.pix0136{idfpix}",
            "qrCodeImgBase64": _FAKE_PNG_B64,
            **record,
            "dataPag": self._now(),
            "nomePesOrgPag": record["nomePesOrg"],
            "docPesOrgPag": record["docPesOrg"],
            "status": "Concluído",
        }

    def list_completed_pix(self, dtaini: str, dtafim: str) -> list[dict[str, Any]]:
        return [
            {
                "idfpix": reference,
                "tipoPessoa": record["tipoPessoa"],
                "docPesOrg": record["docPesOrg"],
                "nomePesOrg": record["nomePesOrg"],
                "valor": record["valor"],
                "dataGeracao": record["dataGeracao"],
                "dataExpiracao": record["dataExpiracao"],
                "dataPag": self._now(),
                "nomePesOrgPag": record["nomePesOrg"],
                "docPesOrgPag": record["docPesOrg"],
            }
            for reference, record in self._records.items()
        ]

    def generate_pdf(self, idfpix: str) -> bytes:
        return _FAKE_PDF

    def generate_qrcode(self, idfpix: str) -> bytes:
        return _FAKE_PNG

    def simulate_payment(self, idfpix: str) -> dict[str, Any]:
        return {"idfpix": idfpix, "status": "Pago"}

    def configure_webhook(self, url: str, token: str) -> dict[str, Any]:
        return {"url": url, "token": token, "configured": True}

    def remove_webhook(self) -> dict[str, Any]:
        return {"removed": True}


def get_pix_gateway() -> PixGateway | FakePixGateway:
    """Seleciona o gateway conforme o modo simulado da stack E2E."""
    if settings.PAYMENT_GATEWAY_FAKE:
        return FakePixGateway()
    return PixGateway()
