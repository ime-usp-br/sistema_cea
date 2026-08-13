import base64
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.models import ServiceApplication
from applications.services import ApplicationSubmissionService
from bank_slips.gateways import BankSlipGatewayError
from bank_slips.models import BankSlipPaymentInstrument
from bank_slips.services import BankSlipDomainError, BankSlipPaymentService
from notifications.models import NotificationDispatch
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.models import User

EAGER = override_settings(CELERY_TASK_ALWAYS_EAGER=True)

_PDF_BYTES = b"%PDF-1.4 mock boleto content"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode("ascii")

SLIP_RESULT = {
    "codigoIDBoleto": "boleto-001",
    "valorDesconto": None,
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

    # Gap 4 — o payload deve enviar ativamente o informacoesBoletoSacado
    def test_TS_BSL_002b_informacoes_boleto_sacado_no_payload(self) -> None:
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
        self.assertIn("informacoesBoletoSacado", captured)
        self.assertEqual(
            captured["informacoesBoletoSacado"],
            "Dúvidas: cea@ime.usp.br",
        )

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
        # O PDF é obtido sob demanda via obterBoleto (docs/BOLETO.md), campo boletoPDF.
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_boleto_pdf",
            return_value=_PDF_B64,
        ):
            self.service.fetch_pdf(slip)
        slip.refresh_from_db()
        asset = slip.pdf_asset
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset.purpose, "bank_slip_pdf")
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

    # TS-BSL-011 — Falha SOAP notifica a equipe CEA (NotifyCEABoletoFailure)
    # ------------------------------------------------------------------

    @EAGER
    def test_TS_BSL_011_falha_soap_notifica_equipe_cea(self) -> None:
        application = self.create_consultation()
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            side_effect=BankSlipGatewayError("timeout"),
        ), self.assertRaises(BankSlipGatewayError):
            self.service.generate_bank_slip_for_fee(
                fee_requirement=self.get_fee(application),
                created_by=self.candidate,
            )
        self.assertEqual(BankSlipPaymentInstrument.objects.count(), 0)
        dispatch = NotificationDispatch.objects.get(
            template__code="bank_slip_generation_failure"
        )
        self.assertEqual(dispatch.recipient_email, "cea@ime.usp.br")
        self.assertEqual(
            dispatch.application_id,
            application.pk,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("timeout", mail.outbox[0].body)

    @EAGER
    def test_TS_BSL_011_sucesso_nao_notifica_falha(self) -> None:
        application = self.create_consultation()
        self.generate_slip(application)
        self.assertEqual(
            NotificationDispatch.objects.filter(
                template__code="bank_slip_generation_failure"
            ).count(),
            0,
        )

    # TS-BSL-GAP-001 — escopo da cron: regenerar apenas Taxa de Inscrição
    def test_TS_BSL_GAP_001_regeneracao_automatica_apenas_para_taxa_de_inscricao(self) -> None:
        """Paridade com o Laravel: a cron NÃO regenere Taxa de Projeto/Complemento."""
        from bank_slips.tasks import regenerate_overdue_bank_slips_task

        application = self.create_consultation()

        # 1. Taxa de Inscrição vencida
        app_fee = self.get_fee(application)
        inst_app = PaymentInstrument.objects.create(
            fee_requirement=app_fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("140.00"),
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=inst_app,
            bank_slip_reference="vencido-inscricao",
            due_date=timezone.localdate() - timedelta(days=2),
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=Decimal("140.00"),
        )

        # 2. Taxa de Projeto vencida (R$ 250,00) — NÃO deve ser regenerada
        proj_fee = FeeRequirement.objects.create(
            application=application,
            fee_type=FeeRequirement.FeeType.PROJECT_FEE,
            base_amount=Decimal("250.00"),
            adjustment_amount=Decimal("0.00"),
            amount=Decimal("250.00"),
            reason="Projeto",
        )
        inst_proj = PaymentInstrument.objects.create(
            fee_requirement=proj_fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("250.00"),
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=inst_proj,
            bank_slip_reference="vencido-projeto",
            due_date=timezone.localdate() - timedelta(days=2),
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=Decimal("250.00"),
        )

        with patch(
            "bank_slips.services.BankSlipPaymentService.regenerate_slip"
        ) as mock_regenerate:
            regenerated_count = regenerate_overdue_bank_slips_task()

        # Deve regenerar 1 (apenas a de inscrição)
        self.assertEqual(regenerated_count, 1)
        mock_regenerate.assert_called_once()
        args, _ = mock_regenerate.call_args
        self.assertEqual(args[0].bank_slip_reference, "vencido-inscricao")

    # TS-BSL-GAP-002 — falha SOAP na reemissão NÃO pode deixar o antigo cancelado
    @EAGER
    def test_TS_BSL_GAP_002_regeneracao_falha_soap_rollback_parcial(self) -> None:
        """Falha ao gerar o novo boleto deve reverter o cancelamento do antigo."""
        application = self.create_consultation()
        fee = self.get_fee(application)
        slip_antigo = self.generate_slip(application)

        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            side_effect=BankSlipGatewayError("SOAP Offline temporariamente"),
        ), self.assertRaises(BankSlipGatewayError):
            self.service.regenerate_slip(
                slip=slip_antigo, created_by=self.candidate
            )

        slip_antigo.refresh_from_db()
        instrumento_antigo = slip_antigo.payment_instrument
        instrumento_antigo.refresh_from_db()
        # O antigo deve permanecer ATIVO (rollback da substituição)
        self.assertEqual(
            instrumento_antigo.state,
            PaymentInstrument.State.ACTIVE,
            "O instrumento antigo foi cancelado sem gerar um substituto (rollback ausente).",
        )
        self.assertEqual(
            slip_antigo.bank_status, BankSlipPaymentInstrument.BankStatus.EMITTED
        )
        # Apenas 1 instrumento ativo na taxa (sem fantasma cancelado)
        self.assertEqual(
            fee.payment_instruments.filter(
                state=PaymentInstrument.State.ACTIVE
            ).count(),
            1,
        )

    # TS-BSL-GAP-004 — falha no MEIO da cron não desfaz boletos já processados
    @EAGER
    def test_TS_BSL_GAP_004_falha_no_meio_da_cron_nao_desfaz_processados(self) -> None:
        """Exceção no 2º boleto não faz rollback do 1º (emails/jobs já disparados)."""
        from bank_slips.tasks import regenerate_overdue_bank_slips_task

        app1 = self.create_consultation()
        app2 = self.create_consultation()
        self._overdue_slip(app1, "vencido-1")
        self._overdue_slip(app2, "vencido-2")

        with patch(
            "bank_slips.gateways.BankSlipGateway.cancelar_boleto", return_value=True
        ), patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            side_effect=[SLIP_RESULT, BankSlipGatewayError("SOAP offline")],
        ), self.assertRaises(BankSlipGatewayError):
            regenerate_overdue_bank_slips_task()

        slips1 = BankSlipPaymentInstrument.objects.filter(
            payment_instrument__fee_requirement__application=app1
        )
        slips2 = BankSlipPaymentInstrument.objects.filter(
            payment_instrument__fee_requirement__application=app2
        )
        all_slips = BankSlipPaymentInstrument.objects.filter(
            payment_instrument__fee_requirement__application__in=[app1, app2]
        )
        # 2 originais + 1 regenerado = 3 (o erro no meio NÃO reverteu o processado)
        self.assertEqual(all_slips.count(), 3)
        # exatamente um app foi regenerado (tem 2 boletos); o outro ficou com 1
        regenerated = sum(1 for c in (slips1.count(), slips2.count()) if c == 2)
        self.assertEqual(regenerated, 1)
        # cada app mantém exatamente 1 instrumento ATIVO (sem fantasma cancelado)
        for app in (app1, app2):
            self.assertEqual(
                BankSlipPaymentInstrument.objects.filter(
                    payment_instrument__fee_requirement__application=app,
                    payment_instrument__state=PaymentInstrument.State.ACTIVE,
                ).count(),
                1,
            )

    def _overdue_slip(
        self, application: ServiceApplication, reference: str
    ) -> BankSlipPaymentInstrument:
        fee = self.get_fee(application)
        instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("140.00"),
        )
        return BankSlipPaymentInstrument.objects.create(
            payment_instrument=instrument,
            bank_slip_reference=reference,
            due_date=timezone.localdate() - timedelta(days=2),
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=Decimal("140.00"),
        )

    # TS-BSL-GAP-003 — secretaria gera boleto primário sem slip existente (Gap D)
    def test_TS_BSL_GAP_003_admin_gera_boleto_primario(self) -> None:
        secretariat = User.objects.create_user(
            username="secretaria_bsl",
            email="sec_bsl@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        application = self.create_consultation()
        self.assertFalse(
            BankSlipPaymentInstrument.objects.filter(
                payment_instrument__fee_requirement__application=application
            ).exists()
        )
        self.client.force_login(secretariat)
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value=SLIP_RESULT,
        ):
            response = self.client.post(
                reverse("bank_slips:admin_generate", args=[application.protocol])
            )
        self.assertEqual(response.status_code, 302)
        slip = BankSlipPaymentInstrument.objects.get(
            payment_instrument__fee_requirement__application=application
        )
        slip.payment_instrument.refresh_from_db()
        self.assertEqual(
            slip.payment_instrument.state, PaymentInstrument.State.ACTIVE
        )

    # TS-BSL-GAP-003b — candidato NÃO pode forçar geração administrativa
    def test_TS_BSL_GAP_003b_candidato_nao_acessa_geracao_admin(self) -> None:
        application = self.create_consultation()
        self.client.force_login(self.candidate)
        response = self.client.post(
            reverse("bank_slips:admin_generate", args=[application.protocol])
        )
        self.assertEqual(response.status_code, 403)

    # TS-BSL-GAP-006 — poller periódico de boletos (paridade Console/Kernel.php)
    def test_TS_BSL_GAP_006b_poller_de_polling_exportado_no_celery(self) -> None:
        from bank_slips.tasks import sync_pending_bank_slips_task

        application = self.create_consultation()
        fee = self.get_fee(application)
        inst = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method=PaymentInstrument.Method.BANK_SLIP,
            state=PaymentInstrument.State.ACTIVE,
            amount=Decimal("140.00"),
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=inst,
            bank_slip_reference="BOL-POLL-1",
            bank_status=BankSlipPaymentInstrument.BankStatus.EMITTED,
            document_amount=Decimal("140.00"),
        )
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_situacao", return_value="P"
        ):
            synced = sync_pending_bank_slips_task()
        self.assertGreaterEqual(synced, 1)
        inst.refresh_from_db()
        self.assertEqual(inst.state, PaymentInstrument.State.PAID)

    # TS-BSL-GAP-007 — regeneração automática avisa a equipe CEA (BCC)
    @EAGER
    def test_TS_BSL_GAP_007_regeneracao_automatica_avisa_equipe_cea(self) -> None:
        """Paridade com o Laravel (RegenerateAndNotifyPaymentFailure):
        a cron regenera o boleto vencido e a equipe CEA recebe a cópia oculta."""
        from bank_slips.tasks import regenerate_overdue_bank_slips_task

        application = self.create_consultation()
        self._overdue_slip(application, "vencido-gap7")

        with patch(
            "bank_slips.gateways.BankSlipGateway.cancelar_boleto", return_value=True
        ), patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value=SLIP_RESULT,
        ):
            regenerate_overdue_bank_slips_task()

        notified_cea = any(
            "cea@ime.usp.br" in (email.bcc or []) for email in mail.outbox
        )
        self.assertTrue(
            notified_cea,
            "A equipe do CEA não foi colocada em cópia (BCC) na regeneração automática.",
        )

    # TS-NOT-GAP-003 — falha do boleto gera aviso de instabilidade no e-mail
    @EAGER
    def test_TS_NOT_GAP_003_aviso_no_email_se_boleto_falhar_na_geracao(self) -> None:
        """Paridade com o ``NotifyInscribedAboutApplication``: se o SOAP cair ao
        gerar o boleto, o candidato recebe a confirmação com alerta de instabilidade."""
        application = self.create_consultation()
        self.client.force_login(self.candidate)
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            side_effect=BankSlipGatewayError("SOAP OFF"),
        ):
            response = self.client.post(
                reverse("bank_slips:generate", args=[application.protocol])
            )
        self.assertEqual(response.status_code, 302)
        # A equipe CEA foi alertada e o candidato recebeu o aviso de instabilidade
        center_fail = NotificationDispatch.objects.get(
            template__code="bank_slip_generation_failure"
        )
        self.assertEqual(center_fail.recipient_email, "cea@ime.usp.br")
        candidate_email = next(
            email for email in mail.outbox if email.to == ["ana@example.com"]
        )
        self.assertIn(
            "instabilidade momentânea",
            candidate_email.body.lower(),
            "O e-mail ao candidato não alertou sobre a falha do boleto.",
        )

    # TS-BSL-GAP-005 — duplo clique "Gerar Boleto" é idempotente (1 ativo por taxa)
    def test_TS_BSL_GAP_005_duplo_click_nao_duplica_boleto(self) -> None:
        application = self.create_consultation()
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value=SLIP_RESULT,
        ):
            first = self.service.generate_bank_slip_for_fee(
                fee_requirement=self.get_fee(application), created_by=self.candidate
            )
            second = self.service.generate_bank_slip_for_fee(
                fee_requirement=self.get_fee(application), created_by=self.candidate
            )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            self.get_fee(application)
            .payment_instruments.filter(state=PaymentInstrument.State.ACTIVE)
            .count(),
            1,
        )


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
        with patch(
            "bank_slips.gateways.BankSlipGateway.obter_boleto_pdf",
            return_value=_PDF_B64,
        ):
            response = self.client.get(f"/boleto/{slip.pk}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        slip.refresh_from_db()
        from django.core.files.storage import default_storage

        assert slip.pdf_asset is not None
        with default_storage.open(slip.pdf_asset.storage_key) as stored:
            self.assertEqual(stored.read(), _PDF_BYTES)
