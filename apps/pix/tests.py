import base64
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from files.models import FileAsset
from payments.models import FeeRequirement, PaymentInstrument
from pix.models import PixPaymentInstrument, PixWebhookEvent
from pix.services import PixPaymentDomainError, PixPaymentService
from terms.models import AcademicTerm
from users.models import User

PIX_RESULT = {
    "idfpix": "pix-abc-123",
    "qrCode": "00020126580014br.gov.bcb.pix0136a4bbf0-000000",
    "qrCodeImgBase64": base64.b64encode(b"qr-png").decode("ascii"),
    "status": "ativo",
    "expiracao": 3600,
}


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-pix-media-"),
    PIX_WEBHOOK_TOKEN="teste-token",
    PIX_EXPIRATION_SECONDS=3600,
)
class PixScenarioTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_pix",
            email="candidate_pix@example.com",
            password="pass",
            tax_id="12345678901",
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.service = PixPaymentService()

    def create_consultation(self) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            researcher_name="João Pix",
            contact_email="joao@example.com",
        )

    def get_fee(self, application: ServiceApplication) -> FeeRequirement:
        return application.fee_requirements.get(
            fee_type=FeeRequirement.FeeType.APPLICATION_FEE
        )

    def generate_pix(self, application: ServiceApplication) -> PixPaymentInstrument:
        with patch("pix.gateways.PixGateway.generate_pix", return_value=PIX_RESULT):
            return self.service.generate_pix_for_fee(
                fee_requirement=self.get_fee(application),
                created_by=self.candidate,
            )

    # ------------------------------------------------------------------
    # TS-PIX-001 — Geração com payload correto
    # ------------------------------------------------------------------

    def test_TS_PIX_001_geracao_com_payload_correto(self) -> None:
        application = self.create_consultation()
        captured: dict = {}

        def fake_generate(payload):
            captured.update(payload)
            return PIX_RESULT

        with patch("pix.gateways.PixGateway.generate_pix", side_effect=fake_generate):
            self.service.generate_pix_for_fee(
                fee_requirement=self.get_fee(application),
                created_by=self.candidate,
            )
        self.assertEqual(captured["valor"], "140,00")
        self.assertEqual(captured["expiracao"], 3600)
        self.assertEqual(captured["tipoPessoa"], "PF")
        self.assertEqual(captured["docPesOrg"], "12345678901")
        self.assertIn("infoCobranca", captured)
        self.assertEqual(
            captured["codigoUnidadeDespesa"], 1
        )

    def test_TS_PIX_001_headers_autenticacao(self) -> None:
        from pix.gateways import PixGateway

        headers = PixGateway()._headers()
        self.assertIn("X-Username", headers)
        self.assertIn("X-Password", headers)

    # ------------------------------------------------------------------
    # TS-PIX-002 — Armazenamento do Pix gerado
    # ------------------------------------------------------------------

    def test_TS_PIX_002_armazenamento_do_pix(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        pix.refresh_from_db()
        self.assertEqual(pix.pix_reference, "pix-abc-123")
        self.assertEqual(pix.qr_code_payload, PIX_RESULT["qrCode"])
        asset = pix.qr_code_image_asset
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset.purpose, "pix_qrcode_image")
        self.assertIsNotNone(pix.generated_at)
        self.assertIsNotNone(pix.expires_at)
        assert pix.generated_at is not None
        assert pix.expires_at is not None
        self.assertEqual(
            pix.expires_at - pix.generated_at, timedelta(seconds=3600)
        )

    def test_TS_PIX_002_pix_ja_gerado_e_reutilizado(self) -> None:
        application = self.create_consultation()
        pix1 = self.generate_pix(application)
        pix2 = self.generate_pix(application)
        self.assertEqual(pix1.pk, pix2.pk)
        self.assertEqual(
            application.fee_requirements.get(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            )
            .payment_instruments.filter(state=PaymentInstrument.State.ACTIVE)
            .count(),
            1,
        )

    # ------------------------------------------------------------------
    # TS-PIX-003 — Consulta com parâmetro verificar
    # ------------------------------------------------------------------

    def test_TS_PIX_003_consulta_atualiza_pagamento(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        with patch(
            "pix.gateways.PixGateway.check_pix_status",
            return_value={"status": "Pago", "valor": "140,00"},
        ):
            self.service.check_pix_status(pix)
        pix.payment_instrument.refresh_from_db()
        self.assertEqual(pix.payment_instrument.state, PaymentInstrument.State.PAID)

    # ------------------------------------------------------------------
    # TS-PIX-004 — Webhook válido
    # ------------------------------------------------------------------

    def test_TS_PIX_004_webhook_valido_confirma_pagamento(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        payload = {"idfpix": pix.pix_reference, "status": "Pago", "valor": "140,00"}
        event = self.service.process_webhook_payload(
            raw_payload=payload, token="teste-token"
        )
        self.assertTrue(event.token_valid)
        self.assertTrue(event.processed)
        pix.payment_instrument.refresh_from_db()
        pix.refresh_from_db()
        self.assertEqual(pix.payment_instrument.state, PaymentInstrument.State.PAID)
        self.assertIsNotNone(pix.paid_at)
        application.refresh_from_db()
        self.assertEqual(
            application.payment_state, ServiceApplication.PaymentState.PAID
        )
        self.assertTrue(
            application.fee_requirements.get(
                fee_type=FeeRequirement.FeeType.APPLICATION_FEE
            ).is_paid
        )
        self.assertTrue(
            application.events.filter(event_code="pix.confirmed").exists()
        )

    # ------------------------------------------------------------------
    # TS-PIX-005 — Webhook com token inválido
    # ------------------------------------------------------------------

    def test_TS_PIX_005_token_invalido_rejeitado(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        payload = {"idfpix": pix.pix_reference, "status": "Pago", "valor": "140,00"}
        event = self.service.process_webhook_payload(
            raw_payload=payload, token="token-errado"
        )
        self.assertFalse(event.token_valid)
        self.assertTrue(event.processed)
        self.assertIsNotNone(event.error_message)
        pix.payment_instrument.refresh_from_db()
        self.assertNotEqual(
            pix.payment_instrument.state, PaymentInstrument.State.PAID
        )
        self.assertNotEqual(application.payment_state, ServiceApplication.PaymentState.PAID)

    # ------------------------------------------------------------------
    # TS-PIX-006 — Webhook duplicado
    # ------------------------------------------------------------------

    def test_TS_PIX_006_webhook_duplicado_idempotente(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        payload = {"idfpix": pix.pix_reference, "status": "Pago", "valor": "140,00"}
        self.service.process_webhook_payload(raw_payload=payload, token="teste-token")
        self.service.process_webhook_payload(raw_payload=payload, token="teste-token")
        pix.payment_instrument.refresh_from_db()
        self.assertEqual(pix.payment_instrument.state, PaymentInstrument.State.PAID)
        self.assertEqual(
            application.events.filter(event_code="pix.confirmed").count(),
            1,
        )

    # ------------------------------------------------------------------
    # TS-PIX-007 — Webhook com valor divergente
    # ------------------------------------------------------------------

    def test_TS_PIX_007_valor_divergente_requer_revisao(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        payload = {"idfpix": pix.pix_reference, "status": "Pago", "valor": "100,00"}
        event = self.service.process_webhook_payload(
            raw_payload=payload, token="teste-token"
        )
        self.assertTrue(event.token_valid)
        self.assertIsNotNone(event.error_message)
        pix.payment_instrument.refresh_from_db()
        self.assertEqual(
            pix.payment_instrument.state, PaymentInstrument.State.REQUIRES_REVIEW
        )
        self.assertTrue(
            application.events.filter(event_code="pix.requires_review").exists()
        )

    # ------------------------------------------------------------------
    # TS-PIX-008 — Webhook de Pix desconhecido
    # ------------------------------------------------------------------

    def test_TS_PIX_008_pix_desconhecido(self) -> None:
        application = self.create_consultation()
        payload = {"idfpix": "nao-existe", "status": "Pago", "valor": "140,00"}
        event = self.service.process_webhook_payload(
            raw_payload=payload, token="teste-token"
        )
        self.assertTrue(event.processed)
        self.assertIsNotNone(event.error_message)
        self.assertNotEqual(application.payment_state, ServiceApplication.PaymentState.PAID)

    # ------------------------------------------------------------------
    # TS-PIX-009 — Reconciliação com listarConcluidos
    # ------------------------------------------------------------------

    def test_TS_PIX_009_reconciliacao_confirma_pagamentos(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        completed = [
            {"idfpix": pix.pix_reference, "status": "Pago", "valor": "140,00"}
        ]
        with patch(
            "pix.gateways.PixGateway.list_completed_pix", return_value=completed
        ):
            count = self.service.reconcile_completed_pix("2026-01-01", "2026-01-10")
        self.assertEqual(count, 1)
        pix.payment_instrument.refresh_from_db()
        self.assertEqual(pix.payment_instrument.state, PaymentInstrument.State.PAID)

    def test_TS_PIX_009_periodo_maior_que_30_dias_rejeitado(self) -> None:
        with self.assertRaises(PixPaymentDomainError):
            self.service.reconcile_completed_pix("2026-01-01", "2026-03-15")

    def test_TS_PIX_009_listarconcluidos_usa_dtaini_dtafim(self) -> None:
        captured: dict[str, str] = {}

        def fake_list(dtaini: str, dtafim: str) -> list:
            captured["dtaini"] = dtaini
            captured["dtafim"] = dtafim
            return []

        with patch(
            "pix.gateways.PixGateway.list_completed_pix", side_effect=fake_list
        ):
            self.service.reconcile_completed_pix("2026-01-01", "2026-01-10")
        self.assertEqual(captured["dtaini"], "01/01/2026 00:00:00")
        self.assertEqual(captured["dtafim"], "10/01/2026 23:59:59")

    # ------------------------------------------------------------------
    # TS-PIX-010 — Simulação de pagamento em desenvolvimento
    # ------------------------------------------------------------------

    def test_TS_PIX_010_simulacao_apenas_em_dev(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        with override_settings(DEBUG=False), self.assertRaises(PixPaymentDomainError):
            self.service.simulate_payment(pix)
        with override_settings(DEBUG=True):
            self.service.simulate_payment(pix)
        pix.payment_instrument.refresh_from_db()
        self.assertEqual(pix.payment_instrument.state, PaymentInstrument.State.PAID)

    # ------------------------------------------------------------------
    # TS-PIX-011 — PDF e QR Code
    # ------------------------------------------------------------------

    def test_TS_PIX_011_qrcode_asset_criado(self) -> None:
        application = self.create_consultation()
        pix = self.generate_pix(application)
        asset = FileAsset.objects.filter(purpose="pix_qrcode_image").first()
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(pix.qr_code_image_asset_id, asset.id)
        assert asset.size_bytes is not None
        self.assertGreater(asset.size_bytes, 0)


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-pix-media-"),
    PIX_WEBHOOK_TOKEN="teste-token",
)
class PixWebhookViewTests(TestCase):
    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_wh",
            email="candidate_wh@example.com",
            password="pass",
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.service = PixPaymentService()

    def create_paid_pix(self) -> PixPaymentInstrument:
        application = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            researcher_name="Maria Webhook",
            contact_email="maria@example.com",
        )
        with patch(
            "pix.gateways.PixGateway.generate_pix", return_value=PIX_RESULT
        ):
            pix = self.service.generate_pix_for_fee(
                fee_requirement=application.fee_requirements.get(
                    fee_type=FeeRequirement.FeeType.APPLICATION_FEE
                ),
                created_by=self.candidate,
            )
        return pix

    def test_webhook_endpoint_confirma_pagamento(self) -> None:
        pix = self.create_paid_pix()
        response = self.client.post(
            "/webhooks/pix/",
            data={
                "idfpix": pix.pix_reference,
                "status": "Pago",
                "valor": "140,00",
            },
            content_type="application/json",
            HTTP_X_TOKEN="teste-token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PixWebhookEvent.objects.filter(pix_reference=pix.pix_reference, token_valid=True).exists())

    def test_webhook_endpoint_token_invalido_rejeitado(self) -> None:
        pix = self.create_paid_pix()
        response = self.client.post(
            "/webhooks/pix/",
            data={
                "idfpix": pix.pix_reference,
                "status": "Pago",
                "valor": "140,00",
            },
            content_type="application/json",
            HTTP_X_TOKEN="errado",
        )
        self.assertEqual(response.status_code, 401)
        event = PixWebhookEvent.objects.get(pix_reference=pix.pix_reference)
        self.assertFalse(event.token_valid)


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-pix-media-"),
    PIX_WEBHOOK_TOKEN="teste-token",
)
class PixDetailViewPermissionTests(TestCase):
    """Autorização da página de detalhe do Pix (pix:detail)."""

    def setUp(self) -> None:
        self.candidate = User.objects.create_user(
            username="candidate_pix_view",
            email="candidate_pix_view@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.other_candidate = User.objects.create_user(
            username="other_candidate_pix_view",
            email="other_candidate_pix_view@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
        )
        self.secretariat = User.objects.create_user(
            username="secretariat_pix_view",
            email="secretariat_pix_view@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.administrator = User.objects.create_user(
            username="admin_pix_view",
            email="admin_pix_view@example.com",
            password="pass",
            role=User.Role.ADMINISTRATOR,
        )
        self.term = AcademicTerm.objects.create(year=2026, period="first")
        self.application = ApplicationSubmissionService().create_application(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            researcher_name="Maria Pix Detail",
            contact_email="maria_detail@example.com",
        )

    def _detail_url(self) -> str:
        return reverse("pix:detail", kwargs={"protocol": self.application.protocol})

    def test_owner_pode_ver_a_pagina(self) -> None:
        self.client.force_login(self.candidate)
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)

    def test_secretaria_e_administrador_podem_ver_a_pagina(self) -> None:
        for staff in (self.secretariat, self.administrator):
            self.client.force_login(staff)
            response = self.client.get(self._detail_url())
            self.assertEqual(response.status_code, 200)

    def test_outro_candidato_nao_pode_ver_a_pagina(self) -> None:
        self.client.force_login(self.other_candidate)
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 404)


class _FakeResponse:
    """Stub mínimo de ``httpx.Response`` para exercitar o gateway real."""

    def __init__(self, payload: object, content: bytes = b"") -> None:
        self._payload = payload
        self.content = content

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        return None


@override_settings(
    PIX_BASE_URL="https://wspix.test/api",
    PIX_USERNAME="consumerdi",
    PIX_PASSWORD="teste1",
)
class PixGatewayContractTests(TestCase):
    """Garante que o PixGateway conversa com o WSPIX no contrato da spec.

    Endpoints verificados (tmp/extracted/pix_spec.txt e docs/PIX.md):
    gerar, consultar, listarConcluidos, pdf, qrcode, simularPag e
    webhookConfig.
    """

    def setUp(self) -> None:
        from pix.gateways import PixGateway

        self.gateway = PixGateway()
        self.calls: list[tuple] = []

    def _patch_request(self, payload: object, content: bytes = b"") -> patch:
        def fake_request(method: str, path: str, *, json_body: dict | None = None, params: dict | None = None):
            self.calls.append((method, path, json_body, params))
            return _FakeResponse(payload, content)

        return patch("pix.gateways.PixGateway._request", side_effect=fake_request)

    def test_gerar_usa_post_pix_gerar_com_autenticacao(self) -> None:
        with self._patch_request({"idfpix": "pix-1", "qrCode": "000201"}):
            result = self.gateway.generate_pix({"tipoPessoa": "PF"})
        self.assertEqual(result["idfpix"], "pix-1")
        method, path, body, _params = self.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "pix/gerar")
        self.assertEqual(body, {"tipoPessoa": "PF"})

    def test_headers_autenticacao_enviados(self) -> None:
        from pix.gateways import PixGateway

        headers = PixGateway()._headers()
        self.assertEqual(headers["X-Username"], "consumerdi")
        self.assertEqual(headers["X-Password"], "teste1")

    def test_consultar_usa_get_por_idfpix(self) -> None:
        with self._patch_request({"status": "Ativo"}):
            result = self.gateway.check_pix_status("pix-1")
        self.assertEqual(result["status"], "Ativo")
        method, path, _body, params = self.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "pix/pix-1")
        self.assertNotIn("verificar", params)

    def test_consultar_com_verificar_envia_query_param(self) -> None:
        with self._patch_request({"status": "Concluído"}):
            self.gateway.check_pix_status("pix-1", verify=True)
        method, path, _body, params = self.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "pix/pix-1")
        self.assertEqual(params, {"verificar": "1"})

    def test_listar_concluidos_usa_dtaini_dtafim(self) -> None:
        with self._patch_request([]):
            result = self.gateway.list_completed_pix("01/08/2026 00:00:00", "25/08/2026 23:59:59")
        self.assertEqual(result, [])
        method, path, _body, params = self.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "pix/listarConcluidos")
        self.assertEqual(params["dtaini"], "01/08/2026 00:00:00")
        self.assertEqual(params["dtafim"], "25/08/2026 23:59:59")

    def test_pdf_qrcode_e_simular_pagamento(self) -> None:
        with self._patch_request(None, b"%PDF"):
            pdf = self.gateway.generate_pdf("pix-1")
        with self._patch_request(None, b"PNG"):
            qr = self.gateway.generate_qrcode("pix-1")
        with self._patch_request({"retorno": "ok"}):
            sim = self.gateway.simulate_payment("pix-1")
        self.assertEqual(pdf, b"%PDF")
        self.assertEqual(qr, b"PNG")
        self.assertEqual(sim["retorno"], "ok")
        methods = [call[0] for call in self.calls]
        paths = [call[1] for call in self.calls]
        self.assertEqual(methods, ["GET", "GET", "PATCH"])
        self.assertEqual(paths, ["pix/pix-1/pdf", "pix/pix-1/qrcode", "pix/pix-1/simularPag"])

    def test_webhook_config_cadastro_e_remocao(self) -> None:
        with self._patch_request({"retorno": "ok", "mensagem": "cadastrado"}):
            result = self.gateway.configure_webhook("https://cea.test/webhooks/pix/", "token-1")
        with self._patch_request({"retorno": "ok"}):
            self.gateway.remove_webhook()
        self.assertIn("mensagem", result)
        first_method, first_path, first_body, _ = self.calls[0]
        self.assertEqual(first_method, "POST")
        self.assertEqual(first_path, "pix/webhookConfig")
        self.assertEqual(first_body, {"url": "https://cea.test/webhooks/pix/", "token": "token-1"})
        second_method, second_path, _body, _ = self.calls[1]
        self.assertEqual(second_method, "DELETE")
        self.assertEqual(second_path, "pix/webhookConfig")
