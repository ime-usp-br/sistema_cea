from __future__ import annotations

import base64
from typing import Any

from django.conf import settings


class BankSlipGatewayError(RuntimeError):
    """Erro de comunicação com o serviço SOAP de boletos."""


class BankSlipGateway:
    """Cliente SOAP para o serviço de emissão de boletos (WS-Boleto, JAX-WS).

    Contrato WS-Boleto (docs/BOLETO.md e tmp/extracted/boleto_spec.txt):

    - WSDL [dev]: ``https://dev.uspdigital.usp.br/wsboleto/wsdl/boleto.wsdl``
    - autenticação: cabeçalhos SOAP ``username``/``password`` (sem namespace)
    - métodos: ``gerarBoletoRegistrado``, ``obterSituacao``, ``obterBoleto``,
      ``cancelarBoleto``, ``obterDetalhe`` e ``registrarBoleto``.

    Usa ``zeep`` de forma lazy dentro dos métodos para que o módulo possa ser
    importado mesmo quando a biblioteca não está instalada (os testes simulam
    completamente as chamadas SOAP).
    """

    # Campos numéricos exigidos pelo XSD (sem ``minOccurs``) mas opcionais na
    # especificação funcional do WS-Boleto. O serviço da USP aceita o valor
    # neutro/zero quando o campo não se aplica à cobrança.
    _XSD_REQUIRED_ZEROS = {
        "codigoConvenio": 0,
        "valorDesconto": 0.0,
        "valorMulta": 0.0,
        "valorDiarioJuros": 0.0,
        "numeroUspSacado": 0,
        "codigoOrganizacaoSacado": 0,
        "numeroUspUsuario": 0,
    }

    def __init__(self, wsdl_url: str | None = None) -> None:
        self.wsdl_url = wsdl_url or settings.BANK_SLIP_WSDL_URL

    def _headers(self) -> dict[str, str]:
        return {
            "username": settings.BANK_SLIP_USERNAME,
            "password": settings.BANK_SLIP_PASSWORD,
        }

    def _soap_header_elements(self) -> list[Any]:
        """Gera os cabeçalhos SOAP ``username``/``password``.

        São elementos sem namespace, como nos exemplos do anexo da
        especificação (SoapUI/Java ``new QName("username")`` e PHP/NuSOAP).
        O WSDL não declara o Header, então os elementos são enviados como
        ``lxml`` puro via ``_soapheaders`` (zeep aceita ``etree._Element``).
        """
        from lxml import etree

        headers: list[Any] = []
        for name, value in self._headers().items():
            element = etree.Element(name)
            element.text = value
            headers.append(element)
        return headers

    def _client(self) -> Any:
        try:
            from zeep import Client
            from zeep.transports import Transport
        except ImportError:  # pragma: no cover
            raise BankSlipGatewayError(
                "A biblioteca zeep não está instalada no ambiente."
            ) from None
        return Client(wsdl=self.wsdl_url, transport=Transport(timeout=30))

    def _call(self, operation: str, **kwargs: Any) -> Any:
        import zeep

        client = self._client()
        try:
            return getattr(client.service, operation)(
                _soapheaders=self._soap_header_elements(),
                **kwargs,
            )
        except zeep.exceptions.Fault as exc:
            raise BankSlipGatewayError(
                f"Falha SOAP em {operation}: {exc}"
            ) from exc
        except Exception as exc:
            raise BankSlipGatewayError(
                f"Falha ao comunicar com o WS-Boleto ({operation}): {exc}"
            ) from exc

    @staticmethod
    def _plain(value: Any) -> Any:
        """Converte o retorno zeep (CompoundValue) em tipos Python simples."""
        from zeep.helpers import serialize_object

        return serialize_object(value, target_cls=dict)

    def gerar_boleto(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Método SOAP ``gerarBoletoRegistrado``.

        Retorna o ``codigoIDBoleto`` que deve ser armazenado para as demais
        operações (obterBoleto, obterSituacao, cancelarBoleto...).
        """
        boleto: dict[str, Any] = {
            key: payload[key]
            for key in (
                "codigoUnidadeDespesa",
                "codigoFonteRecurso",
                "estruturaHierarquica",
                "instrucoesObjetoCobranca",
            )
            if key in payload
        }
        for key, default in self._XSD_REQUIRED_ZEROS.items():
            boleto[key] = payload.get(key, default)
        for key in (
            "nomeFonte",
            "nomeSubfonte",
            "dataVencimentoBoleto",
            "valorDocumento",
            "tipoSacado",
            "cpfCnpj",
            "nomeSacado",
            "cepSacado",
            "numeroEnderecoSacado",
            "complementoEnderecoSacado",
            "codigoEmail",
            "informacoesBoletoSacado",
        ):
            if key in payload and payload[key] not in (None, ""):
                boleto[key] = payload[key]

        result = self._call("gerarBoletoRegistrado", boletoRegistrado=boleto)
        # O WSDL é document/literal wrapped; o zeep desembrulha a cadeia
        # ``gerarBoletoRegistradoResponse > identificacao > codigoIDBoleto``
        # e retorna o ``codigoIDBoleto`` diretamente como string.
        if isinstance(result, str):
            return {"codigoIDBoleto": result}
        plain = self._plain(result)
        if not isinstance(plain, dict):
            plain = {}
        codigo = plain.get("codigoIDBoleto")
        if not codigo and isinstance(plain.get("identificacao"), dict):
            codigo = plain["identificacao"].get("codigoIDBoleto")
        if not codigo:
            codigo = getattr(result, "codigoIDBoleto", None) or ""
        plain["codigoIDBoleto"] = codigo
        return {str(k): v for k, v in plain.items()}

    def obter_situacao(self, codigo_id_boleto: str) -> str:
        """Método SOAP ``obterSituacao``.

        Retorna o status do boleto (E=emitido, P=pago, V=verificar,
        C=cancelado).
        """
        result = self._call(
            "obterSituacao",
            identificacao={"codigoIDBoleto": codigo_id_boleto},
        )
        status = getattr(result, "statusBoletoBancario", None)
        if status is None and isinstance(result, dict):
            status = result.get("statusBoletoBancario")
        status = str(status or "").strip().upper()
        if status not in {"E", "P", "V", "C"}:
            raise BankSlipGatewayError(
                f"Status inesperado do boleto {codigo_id_boleto}: {status!r}"
            )
        return status

    def obter_boleto_pdf(self, codigo_id_boleto: str) -> str:
        """Método SOAP ``obterBoleto``.

        O boleto é retornado em binário Base64 (MTOM) pelo webservice; aqui o
        PDF é devolvido como string Base64, contrato usado pelo serviço local.
        """
        result = self._call(
            "obterBoleto",
            identificacao={"codigoIDBoleto": codigo_id_boleto},
        )
        pdf = (
            result.get("boletoPDF") or b""
            if isinstance(result, dict)
            else result
        )
        if isinstance(pdf, bytes):
            pdf = base64.b64encode(pdf).decode("ascii")
        elif isinstance(pdf, memoryview):
            pdf = base64.b64encode(bytes(pdf)).decode("ascii")
        elif not isinstance(pdf, str):
            pdf = str(pdf)
        return pdf

    def cancelar_boleto(self, codigo_id_boleto: str) -> bool:
        """Método SOAP ``cancelarBoleto``."""
        self._call(
            "cancelarBoleto",
            identificacao={"codigoIDBoleto": codigo_id_boleto},
        )
        return True

    def obter_detalhe(self, codigo_id_boleto: str) -> dict[str, Any]:
        """Método SOAP ``obterDetalhe``.

        Retorna os pares chave-valor usados na impressão do boleto (ex.:
        ``lnhdgv`` = linha digitável, ``vlrcob`` = valor cobrado).
        """
        result = self._call(
            "obterDetalhe",
            identificacao={"codigoIDBoleto": codigo_id_boleto},
        )
        plain = self._plain(result)
        if not isinstance(plain, dict):
            plain = {}
        entries = plain.get("entry") or getattr(result, "entry", None) or []
        detail: dict[str, Any] = {}
        for entry in entries:
            if isinstance(entry, dict):
                key = entry.get("key")
                value = entry.get("value")
            else:
                key = getattr(entry, "key", None)
                value = getattr(entry, "value", None)
            if key:
                detail[str(key)] = value
        return detail

    def registrar_boleto(self, codigo_id_boleto: str) -> str:
        """Método SOAP ``registrarBoleto`` (registra boleto em caso de falha)."""
        result = self._call(
            "registrarBoleto",
            identificacao={"codigoIDBoleto": codigo_id_boleto},
        )
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return str(result.get("mensagem", ""))
        return str(getattr(result, "mensagem", "") or "")
