from typing import Any

from django.conf import settings


class PixGatewayError(RuntimeError):
    """Erro de comunicação com o gateway Pix."""


class PixGateway:
    """Cliente HTTP para o serviço externo de cobrança Pix.

    A integração é feita via API REST/JSON usando ``httpx``. O transporte é
    criado de forma lazy dentro de cada método para que o módulo possa ser
    importado mesmo quando ``httpx`` não está disponível no ambiente (os
    testes simulam completamente essas chamadas).
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or settings.PIX_BASE_URL

    def _headers(self) -> dict[str, str]:
        return {
            "X-Username": settings.PIX_USERNAME,
            "X-Password": settings.PIX_PASSWORD,
        }

    def generate_pix(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /pix/gerar — gera uma cobrança Pix."""
        import httpx

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{self.base_url}/gerar",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise PixGatewayError(f"Falha ao gerar Pix: {exc}") from exc

    def check_pix_status(self, idfpix: str, *, verify: bool = False) -> dict[str, Any]:
        """GET /pix/<idfpix> — consulta o status de uma cobrança."""
        import httpx

        params: dict[str, Any] = {"verificar": "1"} if verify else {}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(
                    f"{self.base_url}/{idfpix}",
                    params=params,
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise PixGatewayError(f"Falha ao consultar Pix: {exc}") from exc

    def list_completed_pix(self, dtaini: str, dtafim: str) -> list[dict[str, Any]]:
        """GET /pix/listarConcluidos — lista Pix pagos em um período.

        Contrato WSPIX (docs/PIX.md): os parâmetros são ``dtaini`` e ``dtafim``
        no formato ``dd/MM/aaaa hh:mm:ss``.
        """
        import httpx

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(
                    f"{self.base_url}/listarConcluidos",
                    params={"dtaini": dtaini, "dtafim": dtafim},
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise PixGatewayError(f"Falha ao listar Pix concluídos: {exc}") from exc
