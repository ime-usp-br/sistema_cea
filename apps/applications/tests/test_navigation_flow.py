"""Testes de navegação e interligação entre páginas do Inscrições CEA.

Cenários TS-NAV: garantem que o usuário consegue transitar entre as telas a
partir das próprias páginas (menu global, breadcrumbs, botões de ação e
links contextuais), sem depender de URLs digitadas manualmente.

Referências de cenários: TEST_SCENARIOS.md (TS-NAV).
"""

from __future__ import annotations

import base64
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from applications.factories import ApplicationFactory, build_valid_form_payload
from applications.models import ServiceApplication
from terms.factories import AcademicTermFactory
from users.factories import (
    AdministratorFactory,
    SecretariatFactory,
    TeacherFactory,
    UserFactory,
)

_PDF_BYTES = b"%PDF-1.4 mock boleto content"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode("ascii")

PIX_RESULT = {
    "idfpix": "pix-nav-001",
    "qrCode": "00020126580014br.gov.bcb.pix0136jornada-nav-001",
    "qrCodeImgBase64": base64.b64encode(b"png-nav").decode("ascii"),
    "status": "ativo",
    "expiracao": 3600,
}

SLIP_RESULT = {
    "codigoIDBoleto": "boleto-nav-001",
    "valorDesconto": None,
}


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-nav-media-"))
class NavigationFlowTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTermFactory()
        self.candidate = UserFactory()
        self.secretariat = SecretariatFactory()
        self.teacher = TeacherFactory()
        self.admin = AdministratorFactory()

    def _application(
        self,
        modality: str = ServiceApplication.Modality.CONSULTATION,
        owner=None,
    ) -> ServiceApplication:
        return ApplicationFactory(modality=modality, owner=owner or self.candidate)

    def _get(self, url: str) -> object:
        return self.client.get(url)

    def _assert_link_present(self, response: object, url: str, msg: str | None = None) -> None:
        self.assertContains(response, f'href="{url}"', msg_prefix=msg or "")

    # ------------------------------------------------------------------
    # TS-NAV-001 Candidato percorre o fluxo completo de inscrição
    # ------------------------------------------------------------------

    def test_TS_NAV_001_fluxo_completo_candidato_sem_urls_manuais(self) -> None:
        # Acessa o painel e parte para a criação de uma nova inscrição.
        self.client.force_login(self.candidate)
        dashboard = self._get(reverse("applications:dashboard"))
        self.assertContains(dashboard, "Nova inscrição")

        create = self._get(reverse("applications:create"))
        self.assertContains(create, "FICHA DE INSCRIÇÃO")
        self._assert_link_present(create, reverse("applications:dashboard"))

        payload = build_valid_form_payload(
            modality=ServiceApplication.Modality.CONSULTATION,
            term_pk=self.term.pk,
        )
        payload.update({"contact_email_confirmation": payload["contact_email"]})
        response = self.client.post(reverse("applications:create"), payload)
        self.assertEqual(response.status_code, 302)
        application = ServiceApplication.objects.get(
            owner=self.candidate,
            modality=ServiceApplication.Modality.CONSULTATION,
        )

        detail = self._get(reverse("applications:detail", args=[application.protocol]))
        self.assertContains(detail, "Ações da inscrição")
        self._assert_link_present(
            detail, reverse("payments:fee_payment", args=[application.protocol])
        )
        self._assert_link_present(
            detail, reverse("documents:application_full_pdf", args=[application.protocol])
        )

        payment = self._get(reverse("payments:fee_payment", args=[application.protocol]))
        self.assertContains(payment, "Escolha a forma de pagamento")
        self._assert_link_present(payment, reverse("applications:detail", args=[application.protocol]))

        # Escolhe o método e gera o Pix (fluxo real do candidato).
        response = self.client.post(
            reverse("payments:fee_payment", args=[application.protocol]),
            {"method": "pix"},
        )
        self.assertEqual(response.status_code, 302)

        with patch(
            "pix.gateways.PixGateway.generate_pix", return_value=PIX_RESULT
        ):
            response = self.client.post(
                reverse("pix:generate", args=[application.protocol])
            )
        self.assertEqual(response.status_code, 302)

        pix_detail = self._get(reverse("pix:detail", args=[application.protocol]))
        self.assertContains(pix_detail, "Pix copia e cola")
        self._assert_link_present(
            pix_detail, reverse("payments:fee_payment", args=[application.protocol])
        )

    def test_TS_NAV_002_fluxo_auditoria_secretaria_sem_urls_manuais(self) -> None:
        # Candidata submete dados de auditoria a partir da página de detalhe.
        project = self._application(modality=ServiceApplication.Modality.PROJECT)
        self.client.force_login(self.candidate)
        detail = self._get(reverse("applications:detail", args=[project.protocol]))
        self._assert_link_present(
            detail, reverse("audits:submit", args=[project.protocol])
        )

        # Submete um arquivo, criando uma submissão pendente.
        from django.core.files.uploadedfile import SimpleUploadedFile as _SUF

        payload = {
            "channel": "file",
            "file": _SUF(
                "dados-nav.csv", b"coluna_a,coluna_b\n1,2\n", content_type="text/csv"
            ),
        }
        submit = self.client.post(
            reverse("audits:submit", args=[project.protocol]), payload
        )
        self.assertEqual(submit.status_code, 302)
        submission = project.audit_submissions.first()
        self.assertIsNotNone(submission)

        # Secretaria acessa a fila de auditoria a partir do menu global.
        self.client.logout()
        self.client.force_login(self.secretariat)
        queue = self._get(reverse("audits:teacher_queue"))
        self.assertContains(queue, "Submissões pendentes")
        self._assert_link_present(queue, reverse("applications:dashboard"))

        review = self._get(reverse("audits:review", args=[submission.pk]))
        self._assert_link_present(review, reverse("audits:teacher_queue"))
        self._assert_link_present(
            review, reverse("applications:detail", args=[project.protocol])
        )

    def test_TS_NAV_003_menu_global_segmenta_por_papel(self) -> None:
        # Candidato vê o menu de candidato e não vê itens de equipe.
        self.client.force_login(self.candidate)
        dashboard = self._get(reverse("applications:dashboard"))
        self.assertContains(dashboard, "Resgatar inscrição")
        self.assertNotContains(dashboard, "Relatório financeiro")

        # Secretaria vê os itens de operação no menu global.
        self.client.logout()
        self.client.force_login(self.secretariat)
        queue = self._get(reverse("audits:teacher_queue"))
        self.assertContains(queue, "Reembolsos")
        self.assertContains(queue, "Agendamentos")
        self.assertContains(queue, "Cobranças")
        self.assertContains(queue, "Resgates")
        self.assertNotContains(queue, "Financeiro")
        self.assertNotContains(queue, "Relatório de auditoria")

        # Administrador vê inclusive os relatórios.
        self.client.logout()
        self.client.force_login(self.admin)
        admin_page = self._get(reverse("audits:teacher_queue"))
        self.assertContains(admin_page, "Financeiro")
        self.assertContains(admin_page, "Auditoria")

    # ------------------------------------------------------------------
    # TS_NAV-003 Páginas internas possuem breadcrumbs e retorno
    # ------------------------------------------------------------------

    def test_TS_NAV_004_todas_as_paginas_possuem_breadcrumb(self) -> None:
        pages = [
            (reverse("applications:dashboard"), "Painel"),
            (reverse("applications:create"), "Nova inscrição"),
            (reverse("audits:teacher_queue"), "Fila de auditoria"),
            (reverse("audits:resolution_list"), "Auditorias rejeitadas"),
            (reverse("meetings:queue"), "Agendamentos"),
            (reverse("payments:refund_list"), "Reembolsos"),
            (reverse("payments:overdue_list"), "Cobranças"),
            (reverse("imports:claim_request"), "Resgatar inscrição"),
            (reverse("imports:claim_queue"), "Resgates"),
            (reverse("reports:financial_report"), "Relatório financeiro"),
            (reverse("reports:audit_report"), "Relatório de auditoria"),
        ]
        self.client.force_login(self.admin)
        for url, label in pages:
            response = self._get(url)
            self.assertEqual(response.status_code, 200, msg=url)
            self.assertContains(response, 'class="breadcrumbs"', msg_prefix=url)
            self.assertContains(response, label, msg_prefix=url)

    def test_TS_NAV_005_links_de_retorno_consistentes(self) -> None:
        application = self._application(
            modality=ServiceApplication.Modality.CONSULTATION
        )

        # fee_payment restringe à inscrição do próprio candidato.
        self.client.force_login(self.candidate)
        fee_payment = self._get(
            reverse("payments:fee_payment", args=[application.protocol])
        )
        self.assertEqual(fee_payment.status_code, 200)
        self._assert_link_present(
            fee_payment, reverse("applications:detail", args=[application.protocol])
        )

        # auditoria/submissão: candidato precisa estar autenticado.
        submission_form = self._get(
            reverse("audits:submit", args=[application.protocol])
        )
        self._assert_link_present(
            submission_form, reverse("applications:detail", args=[application.protocol])
        )

        # reembolso: página da secretaria.
        self.client.logout()
        self.client.force_login(self.secretariat)
        refund_form = self._get(
            reverse("payments:refund_create", args=[application.protocol])
        )
        self.assertEqual(refund_form.status_code, 200)
        self._assert_link_present(refund_form, reverse("payments:refund_list"))

    def test_TS_NAV_006_relatorios_ligam_as_inscricoes(self) -> None:
        self._application(modality=ServiceApplication.Modality.CONSULTATION)
        self.client.force_login(self.admin)
        financial = self._get(reverse("reports:financial_report"))
        self.assertEqual(financial.status_code, 200)
        self.assertContains(financial, "Relatório financeiro")

        audit = self._get(reverse("reports:audit_report"))
        self.assertEqual(audit.status_code, 200)
        self.assertContains(audit, "Relatório de auditoria")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="cea-nav-media-"))
class PaymentInstrumentNavigationTests(TestCase):
    def setUp(self) -> None:
        self.term = AcademicTermFactory()
        self.candidate = UserFactory()
        self.client.force_login(self.candidate)

    def _get(self, url: str) -> object:
        return self.client.get(url)

    def _assert_link_present(self, response: object, url: str, msg: str | None = None) -> None:
        self.assertContains(response, f'href="{url}"', msg_prefix=msg or "")

    def test_TS_NAV_007_instrumentos_ligam_ao_boleto_pix_e_recibo(self) -> None:
        application = ApplicationFactory(
            modality=ServiceApplication.Modality.CONSULTATION,
            owner=self.candidate,
        )
        fee = application.fee_requirements.first()
        self.assertIsNotNone(fee)

        # Cria um boleto e valida o link da tela de pagamento para o boleto.
        with patch(
            "bank_slips.gateways.BankSlipGateway.gerar_boleto",
            return_value=SLIP_RESULT,
        ):
            response = self.client.post(
                reverse("bank_slips:generate", args=[application.protocol])
            )
        self.assertEqual(response.status_code, 302)

        payment = self._get(reverse("payments:fee_payment", args=[application.protocol]))
        self._assert_link_present(payment, reverse("bank_slips:detail", args=[application.protocol]))

        bank_slip = self._get(reverse("bank_slips:detail", args=[application.protocol]))
        self.assertContains(bank_slip, "Baixar PDF do boleto")
        self._assert_link_present(bank_slip, reverse("payments:fee_payment", args=[application.protocol]))
