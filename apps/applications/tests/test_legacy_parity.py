import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.models import ServiceApplication
from bank_slips.models import BankSlipPaymentInstrument
from notifications.models import NotificationDispatch
from payments.models import FeeRequirement, PaymentInstrument
from terms.factories import AcademicTermFactory
from users.factories import SecretariatFactory, UserFactory

EAGER = override_settings(CELERY_TASK_ALWAYS_EAGER=True)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LegacyParityGapsTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTermFactory()
        self.secretariat = SecretariatFactory()
        self.candidate = UserFactory()

    # ------------------------------------------------------------------
    # GAP 1: TRANSFERÊNCIA MANUAL DE SEMESTRE (TermTransferService)
    # ------------------------------------------------------------------
    def test_TS_TRM_006_secretaria_transfere_inscricao_manualmente(self):
        """No Laravel a Secretaria tinha um botão na view para transferir de semestre."""
        self.client.force_login(self.secretariat)
        next_term = AcademicTermFactory(year=2099)

        application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            modality="consultation",
            protocol="888888888",
            researcher_name="Ana Transferencia",
            contact_email=self.candidate.email,
        )

        # Endpoint que existia no Laravel e precisa ser criado no Django (urls.py)
        url = reverse("applications:transfer_semester", args=[application.protocol])
        response = self.client.post(url)

        self.assertRedirects(
            response, reverse("applications:detail", args=[application.protocol])
        )

        application.refresh_from_db()
        self.assertEqual(application.term_id, next_term.id)
        self.assertFalse(application.transfer_pending)

    # ------------------------------------------------------------------
    # GAP 2: NOTIFICAÇÃO DE MUDANÇA DE MODALIDADE (NotifyServiceChange)
    # ------------------------------------------------------------------
    @EAGER
    def test_TS_NOT_011_mudanca_de_modalidade_notifica_candidato(self):
        """O Laravel enviava o email NotifyServiceChange com o novo boleto."""
        from payments.services import FeeCalculationService, ModalityChangeService

        application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            modality="project",
            protocol="999999999",
            contact_email=self.candidate.email,
            researcher_name="Bruno Modalidade",
        )
        FeeCalculationService().create_application_fee(application)

        # Executa o serviço de mudança de modalidade
        ModalityChangeService().convert_to_consultation(
            application=application, decided_by=self.secretariat
        )

        # DEVE existir um despacho de e-mail com o código de template correto
        dispatches = NotificationDispatch.objects.filter(
            application=application,
            template__code="service_modality_changed",  # Template precisa ser adicionado no seeder!
        )
        self.assertTrue(
            dispatches.exists(),
            "O candidato deve ser notificado por e-mail ao sofrer mudança de modalidade pela Secretaria.",
        )

    # ------------------------------------------------------------------
    # GAP 3: PAINEL DE INADIMPLÊNCIA (Overdue Billing)
    # ------------------------------------------------------------------
    def test_TS_PAY_009_secretaria_acessa_painel_de_boletos_vencidos(self):
        """Garante que a tela de cobranças manuais / inadimplência foi portada."""
        self.client.force_login(self.secretariat)

        # A Rota 'payments:overdue_list' precisa ser criada no Django
        url = reverse("payments:overdue_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cobranças Manuais")

    # ------------------------------------------------------------------
    # GAP 4: WORKER DE REGENERAÇÃO (RegenerateAndNotifyPaymentFailure)
    # ------------------------------------------------------------------
    @EAGER
    @patch("bank_slips.gateways.BankSlipGateway.gerar_boleto")
    def test_TS_BSL_012_task_regenera_boletos_vencidos_e_notifica(self, mock_gerar):
        """Testa se a Celery task do Django substitui o script de Cron do Laravel."""
        from bank_slips.tasks import regenerate_overdue_bank_slips_task

        mock_gerar.return_value = {
            "codigoIDBoleto": "novo-boleto-123",
            "valorDesconto": None,
        }

        application = ServiceApplication.objects.create(
            term=self.term,
            owner=self.candidate,
            modality="project",
            protocol="777777777",
            researcher_name="Carla Boleto",
            contact_email=self.candidate.email,
        )
        fee = FeeRequirement.objects.create(
            application=application,
            fee_type="application_fee",
            base_amount=80.00,
            amount=80.00,
        )

        # Cria um instrumento vencido (no passado)
        instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method="bank_slip",
            state="active",
            amount=80.00,
            active_unique_fee_token=fee.pk,
        )
        BankSlipPaymentInstrument.objects.create(
            payment_instrument=instrument,
            bank_slip_reference="boleto-velho",
            due_date=(timezone.now() - timedelta(days=1)).date(),
            bank_status="E",
        )

        # Executa a task Celery que substitui o Cron do Laravel
        regenerated_count = regenerate_overdue_bank_slips_task()

        self.assertEqual(regenerated_count, 1)

        # Verifica se o boleto antigo foi substituído
        instrument.refresh_from_db()
        self.assertEqual(instrument.state, "superseded")

        # Verifica se o e-mail NotifyPaymentFailure foi despachado
        self.assertTrue(
            NotificationDispatch.objects.filter(
                application=application, template__code="payment_failure_regenerated"
            ).exists()
        )
