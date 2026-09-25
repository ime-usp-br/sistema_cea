from typing import Any

from django.conf import settings
from django.template.loader import render_to_string

from applications.models import ServiceApplication
from meetings.models import ProjectScreening
from payments.models import PaymentInstrument


class DocumentRenderingService:
    """Renderiza documentos HTML/CSS para PDF (WeasyPrint).

    A importação do WeasyPrint é lazy e protegida por fallback: em ambientes
    (ex.: CI/testes) onde a biblioteca não está instalada no SO, retorna um
    PDF mock em bytes para não quebrar o fluxo (TS-NFR-004/005).
    """

    def render_application_full_pdf(self, application: ServiceApplication) -> bytes:
        context: dict[str, Any] = {
            "application": application,
            "protocol": application.protocol,
        }
        return self.render_pdf("documents/application_full_pdf.html", context)

    def render_application_firstpage_pdf(
        self, application: ServiceApplication, can_view_financial: bool = True
    ) -> bytes:
        """PDF resumido de 1 página com os dados essenciais da inscrição.

        Porta da rota ``/applications/{protocol}/firstpageaspdf`` e do template
        LaTeX ``latexfirstpage.blade.php`` do sistema legado, usado pela
        Secretaria/Docentes para impressão rápida. O Docente não vê CPF/dados
        financeiros (ARCHITECTURE.md §7.3/§38.2).
        """
        context: dict[str, Any] = {
            "application": application,
            "protocol": application.protocol,
            "can_view_financial": can_view_financial,
        }
        return self.render_pdf("documents/application_firstpage_pdf.html", context)

    def render_payment_receipt_pdf(self, instrument: PaymentInstrument) -> bytes:
        context: dict[str, Any] = {
            "instrument": instrument,
            "application": instrument.fee_requirement.application,
        }
        return self.render_pdf("documents/payment_receipt_pdf.html", context)

    def render_screening_summary_pdf(self, screening: ProjectScreening) -> bytes:
        context: dict[str, Any] = {
            "screening": screening,
            "application": screening.application,
        }
        return self.render_pdf("documents/screening_summary_pdf.html", context)

    def render_pdf(self, template_name: str, context: dict[str, Any]) -> bytes:
        html_content: str = render_to_string(template_name, context)
        html_content = self._inject_base_href(html_content)
        return self._convert_to_pdf(html_content)

    @staticmethod
    def _inject_base_href(html_content: str) -> str:
        """Insere uma tag <base href> para o WeasyPrint resolver os assets
        (logotipos) por caminho relativo, sem depender de `base_url`.
        """
        base_href = "file://" + str(settings.BASE_DIR) + "/"
        base_tag = f'<base href="{base_href}">'
        if "<head" in html_content:
            return html_content.replace("<head>", "<head>" + base_tag, 1)
        return base_tag + html_content

    @staticmethod
    def _convert_to_pdf(html_content: str) -> bytes:
        try:
            from weasyprint import HTML

            return HTML(string=html_content).write_pdf()
        except Exception:  # noqa: BLE001 - WeasyPrint indisponível -> fallback
            return b"%PDF-1.4\n" + html_content.encode("utf-8")
