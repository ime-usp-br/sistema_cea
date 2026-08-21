"""Testes do comando de simulação da jornada (``manage.py simulate_journey``).

O comando percorre a máquina de estados usando os Services reais e mockando
apenas os gateways externos (Pix/Boleto). Estes testes validam que cada etapa
avança o fluxo e produz os eventos de auditoria esperados.
"""

from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase, override_settings

from applications.models import ServiceApplication


def _latest_application(modality: str) -> ServiceApplication:
    return (
        ServiceApplication.objects.filter(owner__username="sim_candidate", modality=modality)
        .order_by("-created_at")
        .first()
    )


class SimulateJourneyCommandProjectTests(TestCase):
    def test_sim_project_pagamento_manual_avanca_para_envio_de_dados(self) -> None:
        call_command("simulate_journey", "--modality", "project", "--submit")
        call_command("simulate_journey", "--modality", "project", "--pay", "--method", "manual")

        app = _latest_application("project")
        self.assertEqual(
            app.lifecycle_status,
            ServiceApplication.LifecycleStatus.AWAITING_DATASET_SUBMISSION,
        )
        self.assertEqual(app.payment_state, ServiceApplication.PaymentState.PAID)
        self.assertTrue(app.events.filter(event_code="payment.manual_confirmed").exists())

    def test_sim_project_jornada_completa_até_aprovado_como_projeto(self) -> None:
        call_command("simulate_journey", "--modality", "project", "--all", "--method", "pix")

        app = _latest_application("project")
        self.assertEqual(
            app.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_PROJECT,
        )
        self.assertEqual(app.payment_state, ServiceApplication.PaymentState.PAID)
        fees = {fee.fee_type: fee for fee in app.fee_requirements.all()}
        self.assertTrue(fees["application_fee"].is_paid)
        self.assertTrue(fees["project_fee"].is_paid)
        self.assertTrue(app.events.filter(event_code="pix.confirmed").exists())
        self.assertTrue(app.events.filter(event_code="meeting.screening_decided").exists())

    def test_sim_project_auditoria_rejeitada_e_inscricao_reprovada(self) -> None:
        call_command("simulate_journey", "--modality", "project", "--submit")
        call_command("simulate_journey", "--modality", "project", "--pay", "--method", "manual")
        call_command("simulate_journey", "--modality", "project", "--submit-dataset")
        call_command("simulate_journey", "--modality", "project", "--review", "rejected")
        call_command("simulate_journey", "--modality", "project", "--resolve", "reject_application")

        app = _latest_application("project")
        self.assertEqual(app.lifecycle_status, ServiceApplication.LifecycleStatus.NOT_APPROVED)
        submission = app.audit_submissions.get()
        self.assertEqual(submission.state, "rejected")
        self.assertEqual(submission.resolutions.get().resolution, "reject_application")

    def test_sim_project_step_1_apenas_cria_inscricao(self) -> None:
        call_command("simulate_journey", "--modality", "project", "--step", "1")

        app = _latest_application("project")
        self.assertEqual(app.lifecycle_status, ServiceApplication.LifecycleStatus.AWAITING_PAYMENT)
        self.assertEqual(app.fee_requirements.count(), 1)


class SimulateJourneyCommandConsultationTests(TestCase):
    def test_sim_consulta_jornada_completa_até_aprovado_como_consulta(self) -> None:
        with override_settings(DEBUG=True):
            call_command(
                "simulate_journey",
                "--modality",
                "consultation",
                "--all",
                "--method",
                "boleto",
            )

        app = _latest_application("consultation")
        self.assertEqual(
            app.lifecycle_status,
            ServiceApplication.LifecycleStatus.APPROVED_AS_CONSULTATION,
        )
        self.assertTrue(app.events.filter(event_code="bank_slip.paid").exists())
        self.assertTrue(app.events.filter(event_code="meeting.consultation_decided").exists())

    def test_sim_consulta_reuniao_aprova_como_projeto(self) -> None:
        call_command("simulate_journey", "--modality", "consultation", "--submit")
        call_command("simulate_journey", "--modality", "consultation", "--pay", "--method", "manual")
        call_command("simulate_journey", "--modality", "consultation", "--schedule-consultation")
        app_before = _latest_application("consultation")
        protocol = app_before.protocol
        call_command(
            "simulate_journey",
            "--modality",
            "consultation",
            "--consultation-decision",
            "approved_as_project",
        )

        # A reunião converte a inscrição para Projeto e cria a Taxa de Projeto.
        app = ServiceApplication.all_objects.get(protocol=protocol)
        self.assertEqual(app.modality, ServiceApplication.Modality.PROJECT)
        self.assertEqual(app.lifecycle_status, ServiceApplication.LifecycleStatus.AWAITING_PAYMENT)
        project_fee = app.fee_requirements.filter(fee_type="project_fee").first()
        self.assertIsNotNone(project_fee)
        self.assertFalse(project_fee.is_paid)


class SimulateJourneyCommandMiscTests(TestCase):
    def test_sim_refund_marca_payment_state_refunded(self) -> None:
        call_command("simulate_journey", "--modality", "project", "--submit")
        call_command("simulate_journey", "--modality", "project", "--pay", "--method", "manual")
        call_command("simulate_journey", "--modality", "project", "--refund")

        app = _latest_application("project")
        self.assertEqual(app.payment_state, ServiceApplication.PaymentState.REFUNDED)
        request = app.refund_requests.get()
        self.assertEqual(request.status, "executed")
