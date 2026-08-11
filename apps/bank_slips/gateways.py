from typing import Any

from django.conf import settings


class BankSlipGatewayError(RuntimeError):
    """Erro de comunicação com o serviço SOAP de boletos."""


class BankSlipGateway:
    """Cliente SOAP para o serviço de emissão de boletos (WSDL).

    Usa ``zeep`` de forma lazy dentro dos métodos para que o módulo possa ser
    importado mesmo quando a biblioteca não está instalada (os testes simulam
    completamente as chamadas SOAP).
    """

    def __init__(self, wsdl_url: str | None = None) -> None:
        self.wsdl_url = wsdl_url or settings.BANK_SLIP_WSDL_URL

    def _headers(self) -> dict[str, str]:
        return {
            "username": settings.BANK_SLIP_USERNAME,
            "password": settings.BANK_SLIP_PASSWORD,
        }

    def gerar_boleto(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Método SOAP ``gerarBoletoRegistrado``."""
        import zeep

        try:
            client = zeep.Client(wsdl=self.wsdl_url)
            return client.service.gerarBoletoRegistrado(
                **payload,
                _soapheaders=self._headers(),
            )
        except Exception as exc:
            raise BankSlipGatewayError(f"Falha ao gerar boleto: {exc}") from exc

    def obter_situacao(self, codigo_id_boleto: str) -> str:
        """Método SOAP ``obterSituacao``. Retorna um status (E/P/V/C)."""
        import zeep

        try:
            client = zeep.Client(wsdl=self.wsdl_url)
            return str(
                client.service.obterSituacao(
                    codigoIdBoleto=codigo_id_boleto,
                    _soapheaders=self._headers(),
                )
            )
        except Exception as exc:
            raise BankSlipGatewayError(f"Falha ao consultar situação: {exc}") from exc

    def obter_boleto_pdf(self, codigo_id_boleto: str) -> str:
        """Método SOAP ``obterBoleto``. Retorna o PDF em Base64."""
        import zeep

        try:
            client = zeep.Client(wsdl=self.wsdl_url)
            return str(
                client.service.obterBoleto(
                    codigoIdBoleto=codigo_id_boleto,
                    _soapheaders=self._headers(),
                )
            )
        except Exception as exc:
            raise BankSlipGatewayError(f"Falha ao obter PDF do boleto: {exc}") from exc

    def cancelar_boleto(self, codigo_id_boleto: str) -> bool:
        """Método SOAP ``cancelarBoleto``."""
        import zeep

        try:
            client = zeep.Client(wsdl=self.wsdl_url)
            client.service.cancelarBoleto(
                codigoIdBoleto=codigo_id_boleto,
                _soapheaders=self._headers(),
            )
            return True
        except Exception as exc:
            raise BankSlipGatewayError(f"Falha ao cancelar boleto: {exc}") from exc
