"""Testes das telas da Secretaria alinhadas ao legado (Fase 2, 4 e 8 do plano).

Cobrem: lista de inscrições com default de semestre atual, lixeira (excluídas
+ restauração), trilha de auditoria por semestre (``Histórico``) e visibilidade
de CPF/financeiro por papel.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from applications.models import ApplicationEvent, ServiceApplication
from applications.services import ApplicationSubmissionService
from terms.models import AcademicTerm
from users.models import User


class SecretariaScreenTests(TestCase):
    def setUp(self) -> None:
        self.term_first = AcademicTerm.objects.create(year=2026, period="first")
        self.term_second = AcademicTerm.objects.create(year=2026, period="second")
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass",
            role=User.Role.CANDIDATE,
            full_name="Dona da Ficha",
        )
        self.secretariat = User.objects.create_user(
            username="sec",
            email="sec@example.com",
            password="pass",
            role=User.Role.SECRETARIAT,
        )
        self.teacher = User.objects.create_user(
            username="doc",
            email="doc@example.com",
            password="pass",
            role=User.Role.TEACHER,
        )

    def _create(
        self,
        term: AcademicTerm,
        *,
        tax_id: str | None = None,
    ) -> ServiceApplication:
        return ApplicationSubmissionService().create_application(
            term=term,
            owner=self.owner,
            modality="project",
            researcher_name="Pesquisadora Teste",
            contact_email="owner@example.com",
            tax_id=tax_id,
        )

    # TS-APP-LISTA-DEFAULT
    def test_TS_APP_LISTA_default_e_semestre_atual(self) -> None:
        """Sem ``?term=``, a lista usa o semestre atual (segundo de 2026)."""
        in_first = self._create(self.term_first)
        in_second = self._create(self.term_second)
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("applications:list"))
        self.assertContains(response, in_second.protocol)
        self.assertNotContains(response, in_first.protocol)

    # TS-APP-LIxeIRA-001
    def test_TS_APP_LIXEIRA_mostra_excluidas_e_esconde_da_lista(self) -> None:
        app = self._create(self.term_second)
        app.soft_delete()
        self.client.force_login(self.secretariat)
        list_response = self.client.get(reverse("applications:list"))
        self.assertNotContains(list_response, app.protocol)
        deleted_response = self.client.get(reverse("applications:deleted_list"))
        self.assertContains(deleted_response, app.protocol)
        self.assertContains(deleted_response, "Restaurar")

    # TS-APP-RESTORE-001
    def test_TS_APP_RESTORE_recupera_inscricao_e_registra_evento(self) -> None:
        app = self._create(self.term_second)
        app.soft_delete()
        self.client.force_login(self.secretariat)
        response = self.client.post(
            reverse("applications:restore", args=[app.protocol])
        )
        self.assertRedirects(response, reverse("applications:deleted_list"))
        app.refresh_from_db()
        self.assertIsNone(app.soft_deleted_at)
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=app, event_code="application.restored"
            ).exists()
        )

    # TS-APP-DOC-CPF-OCULTO
    def test_TS_APP_DOCENTE_nao_ve_cpf_nem_financeiro_na_ficha(self) -> None:
        app = self._create(self.term_second, tax_id="123.456.789-01")
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("applications:detail", args=[app.protocol]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "123.456.789-01")
        self.assertNotContains(response, "Financeiro")

    # TS-APP-DOC-CPF-OCULTO (variação) — dono e Secretaria veem
    def test_TS_APP_SECRETARIA_ve_cpf_e_financeiro_na_ficha(self) -> None:
        app = self._create(self.term_second, tax_id="123.456.789-01")
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("applications:detail", args=[app.protocol]))
        self.assertContains(response, "123.456.789-01")
        self.assertContains(response, "Financeiro")

    # TS-APP-EVENTOS-POR-SEMESTRE
    def test_TS_APP_EVENTOS_filtra_por_semestre_atual(self) -> None:
        in_first = self._create(self.term_first)
        in_second = self._create(self.term_second)
        in_second.events.create(
            event_code="test", description="evento do segundo semestre"
        )
        in_first.events.create(event_code="test", description="evento do primeiro")
        self.client.force_login(self.secretariat)
        response = self.client.get(reverse("applications:event_list"))
        self.assertContains(response, "evento do segundo semestre")
        self.assertNotContains(response, "evento do primeiro")

    # TS-APP-PDF-LEGADO
    def test_TS_APP_PDF_full_contem_itens_do_legado(self) -> None:
        from unittest.mock import patch

        from applications.factories import ApplicationFactory
        from documents.services import DocumentRenderingService

        application = ApplicationFactory(
            modality=ServiceApplication.Modality.PROJECT,
            term=self.term_second,
        )
        with patch.object(
            DocumentRenderingService,
            "_convert_to_pdf",
            staticmethod(lambda html: html.encode("utf-8")),
        ):
            content = DocumentRenderingService().render_application_full_pdf(
                application
            ).decode("utf-8")
        self.assertIn("A SER PREENCHIDO PELO CEA", content)
        self.assertIn("Data da 1ª reunião:", content)
        self.assertIn("Decisão:", content)
        self.assertIn("9. Que tipo de ajuda você espera do CEA?", content)
        self.assertIn("Não foram feitos anexos.", content)
        self.assertIn("Data da inscrição:", content)
        self.assertIn("Vínculo com a Instituição:", content)
        self.assertIn("Finalidade do projeto:", content)
        self.assertIn("Área de conhecimento:", content)
