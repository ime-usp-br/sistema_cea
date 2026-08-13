from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from applications.models import ServiceApplication
from meetings.models import ProjectScreening
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.models import User

from .services import DocumentRenderingService

LONG_TEXT = (
    "Este é um texto muito longo com múltiplas linhas para validar a quebra de "
    "linha nos campos livres do PDF. " * 20
)
SPECIAL_CHARS = (
    "Símbolos & < > % $ # ^ ~ e acentuação: ção á é í ó ú â ê ô ã õ à. "
)


def _capture_html(html: str) -> bytes:
    """Retorna o HTML como bytes para inspeção nos testes (sem WeasyPrint)."""
    return html.encode("utf-8")


class DocumentRenderingServiceTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate1",
            email="candidate@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            protocol="123456789",
            modality=ServiceApplication.Modality.PROJECT,
            researcher_name="Maria Pesquisadora",
            contact_email="candidate@example.com",
            project_title=SPECIAL_CHARS,
            context_summary=LONG_TEXT,
            general_objectives=LONG_TEXT,
        )
        self.fee = FeeRequirement.objects.create(
            application=self.application,
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE,
            base_amount=Decimal("80.00"),
            adjustment_amount=Decimal("0.00"),
            amount=Decimal("80.00"),
            reason="Taxa de inscrição",
        )
        self.instrument = PaymentInstrument.objects.create(
            fee_requirement=self.fee,
            method=PaymentInstrument.Method.PIX,
            state=PaymentInstrument.State.PAID,
            amount=Decimal("80.00"),
        )
        self.screening = ProjectScreening.objects.create(
            application=self.application,
            scheduled_date=date(2099, 1, 1),
            scheduled_time=time(10, 0),
            meeting_mode="online",
            virtual_link="https://meet.example.com/sala",
            state=ProjectScreening.State.SCHEDULED,
        )
        self.service = DocumentRenderingService()

    def _html(self, method_name: str) -> str:
        with patch.object(
            DocumentRenderingService,
            "_convert_to_pdf",
            staticmethod(_capture_html),
        ):
            method = getattr(self.service, method_name)
            pdf_bytes = method(self.application)
        return pdf_bytes.decode("utf-8")

    def test_render_application_full_pdf_generates_bytes(self) -> None:
        with patch.object(
            DocumentRenderingService, "_convert_to_pdf", staticmethod(_capture_html)
        ):
            result = self.service.render_application_full_pdf(self.application)
        self.assertIsInstance(result, bytes)
        self.assertIn("Ficha de Inscrição", result.decode("utf-8"))

    def test_render_payment_receipt_pdf_generates_bytes(self) -> None:
        with patch.object(
            DocumentRenderingService, "_convert_to_pdf", staticmethod(_capture_html)
        ):
            result = self.service.render_payment_receipt_pdf(self.instrument)
        self.assertIsInstance(result, bytes)
        self.assertIn("Comprovante de Pagamento", result.decode("utf-8"))

    def test_render_screening_summary_pdf_generates_bytes(self) -> None:
        with patch.object(
            DocumentRenderingService, "_convert_to_pdf", staticmethod(_capture_html)
        ):
            result = self.service.render_screening_summary_pdf(self.screening)
        self.assertIsInstance(result, bytes)
        self.assertIn("Resumo de Triagem", result.decode("utf-8"))

    def test_pdf_fallback_sem_weasyprint_retorna_mock(self) -> None:
        html = "<html><body>OK</body></html>"
        result = DocumentRenderingService._convert_to_pdf(html)
        self.assertTrue(result.startswith(b"%PDF-1.4"))

    # TS-NFR-004
    def test_TS_NFR_004_textos_longos_quebram_linha(self) -> None:
        html = self._html("render_application_full_pdf")
        self.assertIn("white-space: pre-wrap;", html)
        self.assertIn("overflow-wrap: anywhere;", html)
        self.assertIn(LONG_TEXT[:80], html)

    # TS-NFR-005
    def test_TS_NFR_005_caracteres_especiais_escapados(self) -> None:
        html = self._html("render_application_full_pdf")
        self.assertIn("Símbolos &amp;", html)
        self.assertIn("&lt; &gt;", html)
        self.assertIn("acentuação: ção", html)

    # TS-NFR-006
    def test_TS_NFR_006_pdf_contem_dados_bancarios_e_de_reembolso(self) -> None:
        self.application.refund_bank_name = "Banco do Brasil"
        self.application.refund_branch_number = "1234"
        self.application.refund_bank_account_number = "99999-X"
        self.application.refund_receipt_details = (
            "Aos cuidados do departamento financeiro do Instituto XYZ"
        )
        self.application.wants_refund_receipt = True
        self.application.save()

        html = self._html("render_application_full_pdf")
        self.assertIn("Banco do Brasil", html)
        self.assertIn("1234", html)
        self.assertIn("99999-X", html)
        self.assertIn("Aos cuidados do departamento financeiro", html)

    # TS-NFR-006 (variação) — sem recibo, bloco não é impresso
    def test_TS_NFR_006_sem_recibo_nao_imprime_dados_bancarios(self) -> None:
        self.application.wants_refund_receipt = False
        self.application.save()

        html = self._html("render_application_full_pdf")
        self.assertNotIn("Dados Bancários", html)
        self.assertNotIn("Recibo para Reembolso", html)


class DocumentDownloadViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.owner,
            protocol="987654321",
            modality=ServiceApplication.Modality.PROJECT,
            researcher_name="Pesquisadora",
            contact_email="owner@example.com",
        )

    def test_ficha_owner_pode_baixar(self) -> None:
        with patch.object(
            DocumentRenderingService, "_convert_to_pdf", staticmethod(_capture_html)
        ):
            self.client.force_login(self.owner)
            response = self.client.get(
                reverse(
                    "documents:application_full_pdf",
                    kwargs={"protocol": self.application.protocol},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_ficha_outro_candidato_nao_pode_baixar(self) -> None:
        self.client.force_login(self.other)
        response = self.client.get(
            reverse(
                "documents:application_full_pdf",
                kwargs={"protocol": self.application.protocol},
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_ficha_exige_login(self) -> None:
        response = self.client.get(
            reverse(
                "documents:application_full_pdf",
                kwargs={"protocol": self.application.protocol},
            )
        )
        self.assertEqual(response.status_code, 302)
