import base64
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from bank_slips.gateways import BankSlipGatewayError
from bank_slips.models import BankSlipPaymentInstrument
from bank_slips.services import BankSlipDomainError, BankSlipPaymentService
from files.models import FileAsset
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.models import User

_PDF_BYTES = b"%PDF-1.4 mock boleto content"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode("ascii")

SLIP_RESULT = {
    "codigoIDBoleto": "boleto-001",
    "valorDesconto": None,
    "pdfBase64": _PDF_B64,
}


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-bsl-media-"),
    BANK_SLIP_DUE_DAYS=3,
)
class BankSlipScenarioTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_bsl",
            email="candidate_bsl@example.com",
            password="pass",
            tax_id="98765432109",
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.service = BankSlipPaymentService()

    def create_consultation(self) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            researcher_name="Ana Boleto",
            contact_email="ana@example.com",
        )

    def get_fee(self, application: ServiceApplication) -> FeeRequirement:
        return application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )

    def generate_slip(self, application: ServiceApplication) -> BankSlipPaymentInstrument:
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value=SLIP_RESULT,
        ):
            return self.service.generate_bank_slip_for_fee(
                fee_requirement=self.get_fee(application),
                created_by=self.candidate,
            )

    # ------------------------------------------------------------------
    # TS-BSL-001 — Geração de boleto registrado
    # ------------------------------------------------------------------

    def test_TS_BSL_001_geracao_boleto_registrado(self) -> None:
        application = self.create_consultation()
        captured: dict = {}

        def fake_gerar(payload):
            captured.update(payload)
            return SLIP_RESULT

        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            side_effect=fake_gerar,
        ):
            slip = self.service.generate_bank_slip_for_fee(
                fee_requirement=self.get_fee(application),
                created_by=self.candidate,
            )
        self.assertEqual(captured["valorDocumento"], "140.00")
        self.assertEqual(len(captured["dataVencimentoBoleto"]), 10)
        self.assertEqual(slip.bank_slip_reference, "boleto-001")
        self.assertEqual(slip.bank_status, BankSlipPaymentInstrument.BankStatus.EMITTED)
        self.assertIsNotNone(slip.due_date)

    def test_TS_BSL_001_headers_soap(self) -> None:
        from bank_slips.gateways import BankSlipGateway

        headers = BankSlipGateway()._headers()
        self.assertIn("username", headers)
        self.assertIn("password", headers)

    # ------------------------------------------------------------------
    # TS-BSL-002 — Dados obrigatórios do boleto
    # ------------------------------------------------------------------

    def test_TS_BSL_002_dados_obrigatorios(self) -> None:
        application = self.create_consultation()
        captured: dict = {}

        def fake_gerar(payload):
            captured.update(payload)
            return SLIP_RESULT

        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            side_effect=fake_gerar,
        ):
            self.service.generate_bank_slip_for_fee(
                fee_requirement=self.get_fee(application),
                created_by=self.candidate,
            )
        self.assertIn("codigoUnidadeDespesa", captured)
        self.assertIn("codigoFonteRecurso", captured)
        self.assertIn("estruturaHierarquica", captured)
        self.assertIn("instrucoesObjetoCobranca", captured)
        self.assertEqual(captured["cpfCnpj"], "98765432109")
        self.assertEqual(captured["tipoSacado"], "PF")

    # ------------------------------------------------------------------
    # TS-BSL-003 — Consulta de situação
    # ------------------------------------------------------------------

    def test_TS_BSL_003_situacao_convertida(self) -> None:
        cases = [
            ("E", BankSlipPaymentInstrument.BankStatus.EMITTED),
            ("P", BankSlipPaymentInstrument.BankStatus.PAID),
            ("V", BankSlipPaymentInstrument.BankStatus.VERIFY),
            ("C", BankSlipPaymentInstrument.BankStatus.CANCELED),
        ]
        for idx, (status, expected_bank) in enumerate(cases):
            with self.subTest(status=status):
                application = self.create_consultation()
                result = dict(SLIP_RESULT)
                result["codigoIDBoleto"] = f"boleto-00{idx}"
                with patch(
                    "bank_slips.gateways.BankSlipGateway.gerar_boleto",
                    return_value=result,
                ):
                    slip = self.service.generate_bank_slip_for_fee(
                        fee_requirement=self.get_fee(application),
                        created_by=self.candidate,
                    )
                with patch(
                    "bank_slips.gateways.BankSlipGateway.obter_situacao",
                    return_value=status,
                ):
                    self.service.sync_bank_slip_status(slip)
                slip.refresh_from_db()
                self.assertEqual(slip.bank_status, expected_bank)

    # ------------------------------------------------------------------
    # TS-BSL-004 — Status V não confirma pagamento
    # ------------------------------------------------------------------

    def test_TS_BSL_004_status_v_nao_confirma(self) -> None:
        application = self.create_consultation()
        slip = self.generate_slip(application)
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao",
            return_value="V",
        ):
            self.service.sync_bank_slip_status(slip)
        slip.payment_instrument.refresh_from_db()
        self.assertEqual(
            slip.payment_instrument.state, PaymentInstrument.State.REQUIRES_REVIEW
        )
        self.assertNotEqual(application.payment_state, ServiceApplication.PaymentState.PAID)

    # ------------------------------------------------------------------
    # TS-BSL-005 — Boleto pago atualiza fluxo
    # ------------------------------------------------------------------

    def test_TS_BSL_005_pago_atualiza_fluxo(self) -> None:
        application = self.create_consultation()
        slip = self.generate_slip(application)
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao",
            return_value="P",
        ):
            self.service.sync_bank_slip_status(slip)
        slip.payment_instrument.refresh_from_db()
        self.assertEqual(slip.payment_instrument.state, PaymentInstrument.State.PAID)
        self.assertIsNotNone(slip.payment_date)
        self.assertEqual(application.payment_state, ServiceApplication.PaymentState.PAID)
        self.assertTrue(
            application.events.filter(event_code="bank_slip.paid").exists()
        )

    # ------------------------------------------------------------------
    # TS-BSL-006 — Download de PDF
    # ------------------------------------------------------------------

    def test_TS_BSL_006_pdf_gerado_e_armazenado(self) -> None:
        application = self.create_consultation()
        slip = self.generate_slip(application)
        asset = FileAsset.objects.filter(purpose="bank_slip_pdf").first()
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(slip.pdf_asset_id, asset.id)
        self.assertEqual(asset.content_type, "application/pdf")

    # ------------------------------------------------------------------
    # TS-BSL-007 — Cancelamento de boleto substituído
    # ------------------------------------------------------------------

    def test_TS_BSL_007_cancelamento(self) -> None:
        application = self.create_consultation()
        slip = self.generate_slip(application)
        with patch(
            "bank_slips.gateways.BankSlipGateway.cancelar_boleto",
            return_value=True,
        ):
            self.service.cancel_bank_slip(slip)
        slip.payment_instrument.refresh_from_db()
        self.assertEqual(
            slip.payment_instrument.state, PaymentInstrument.State.CANCELED
        )
        self.assertEqual(slip.bank_status, BankSlipPaymentInstrument.BankStatus.CANCELED)
        self.assertIsNotNone(slip.cancellation_date)

    # ------------------------------------------------------------------
    # TS-BSL-008 — Consulta em lote
    # ------------------------------------------------------------------

    def test_TS_BSL_008_consulta_em_lote(self) -> None:
        application = self.create_consultation()
        slip_a = self.generate_slip(application)
        slip_b = self.generate_slip(application)
        self.assertEqual(slip_a.pk, slip_b.pk, "boleto ativo deve ser reutilizado")
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao",
            return_value="P",
        ):
            self.service.sync_bank_slip_status(slip_a)
        slip_b.refresh_from_db()
        self.assertEqual(slip_b.payment_instrument.state, PaymentInstrument.State.PAID)

    # ------------------------------------------------------------------
    # TS-BSL-009 — Falha SOAP
    # ------------------------------------------------------------------

    def test_TS_BSL_009_falha_soap_nao_grava_inconsistencia(self) -> None:
        application = self.create_consultation()
        slip = self.generate_slip(application)
        initial_state = slip.payment_instrument.state
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao",
            side_effect=BankSlipGatewayError("timeout"),
        ), self.assertRaises(BankSlipGatewayError):
            self.service.sync_bank_slip_status(slip)
        slip.payment_instrument.refresh_from_db()
        self.assertEqual(slip.payment_instrument.state, initial_state)
        self.assertEqual(slip.bank_status, BankSlipPaymentInstrument.BankStatus.EMITTED)

    # ------------------------------------------------------------------
    # TS-BSL-010 — Simulação de pagamento em desenvolvimento
    # ------------------------------------------------------------------

    def test_TS_BSL_010_simulacao_apenas_em_dev(self) -> None:
        application = self.create_consultation()
        slip = self.generate_slip(application)
        with override_settings(DEBUG=False), self.assertRaises(BankSlipDomainError):
            self.service.simulate_payment(slip)
        with override_settings(DEBUG=True):
            self.service.simulate_payment(slip)
        slip.payment_instrument.refresh_from_db()
        self.assertEqual(slip.payment_instrument.state, PaymentInstrument.State.PAID)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-bsl-media-"))
class BankSlipPdfViewTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_pdf",
            email="candidate_pdf@example.com",
            password="pass",
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.service = BankSlipPaymentService()

    def create_slip(self) -> BankSlipPaymentInstrument:
        application = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            researcher_name="PDF Boleto",
            contact_email="pdf@example.com",
        )
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value=SLIP_RESULT,
        ):
            return self.service.generate_bank_slip_for_fee(
                fee_requirement=application.fee_requirements.get(
                    fee_type=FeeRequirement.FeeType.APPLICATION_FEE
                ),
                created_by=self.candidate,
            )

    def test_download_pdf_endpoint_retorna_pdf(self) -> None:
        slip = self.create_slip()
        self.client.force_login(self.candidate)
        response = self.client.get(f"/boleto/{slip.pk}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        response.close()
        from django.core.files.storage import default_storage

        assert slip.pdf_asset is not None
        with default_storage.open(slip.pdf_asset.storage_key) as stored:
            self.assertEqual(stored.read(), _PDF_BYTES)
