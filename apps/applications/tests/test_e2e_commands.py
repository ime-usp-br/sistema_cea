"""Testes dos comandos de apoio à stack E2E (setup, inspeção e caixa de e-mail)."""

from __future__ import annotations

import io
import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from applications.models import ServiceApplication
from bank_slips.models import BankSlipPaymentInstrument
from payments.models import FeeRequirement, PaymentInstrument
from terms.models import AcademicTerm
from users.models import User


def _call(*args: str) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out, stderr=io.StringIO())
    return out.getvalue()


@override_settings(DEBUG=True)
class SeedAndInspectionCommandsTests(TestCase):
    # TST-APP-012
    def test_seed_e2e_cria_usuarios_verificados_e_admin(self) -> None:
        output = _call("seed_e2e")
        data = json.loads(output.strip().splitlines()[-1])
        self.assertEqual(data["users"]["admin"], "e2e_admin")
        admin = User.objects.get(username="e2e_admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_email_verified)
        self.assertEqual(
            User.objects.get(username="e2e_candidate").role, User.Role.CANDIDATE
        )

    # TST-APP-013
    def test_e2e_environment_expoe_configuracao_de_mock(self) -> None:
        with override_settings(
            PAYMENT_GATEWAY_FAKE=True,
            CELERY_TASK_ALWAYS_EAGER=True,
            EMAIL_BACKEND="django.core.mail.backends.filebased.EmailBackend",
        ):
            data = json.loads(_call("e2e_environment", "--json"))
        self.assertTrue(data["payment_gateway_fake"])
        self.assertEqual(data["pix_gateway"], "FakePixGateway")
        self.assertEqual(data["bank_slip_gateway"], "FakeBankSlipGateway")
        self.assertTrue(data["celery_task_always_eager"])

    # TST-APP-014
    def test_e2e_create_term_e_idempotente(self) -> None:
        first = json.loads(_call("e2e_create_term", "--year", "2099"))
        second = json.loads(_call("e2e_create_term", "--year", "2099"))
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["id"], second["id"])

    # TST-APP-015
    def test_e2e_create_term_auto_e_peek_no_namespace(self) -> None:
        peek = json.loads(_call("e2e_create_term", "--peek"))
        created = json.loads(_call("e2e_create_term", "--auto"))
        self.assertEqual(created["year"], peek["year"])
        self.assertTrue(created["created"])
        self.assertEqual(json.loads(_call("e2e_create_term", "--peek"))["year"], peek["year"] + 1)

    # TST-APP-016
    def test_e2e_create_user_candidato_verificado_e_recusa_duplicado(self) -> None:
        first = json.loads(
            _call("e2e_create_user", "--suffix", "run-001")
        )
        self.assertTrue(first["created"])
        user = User.objects.get(username=first["username"])
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertTrue(user.is_email_verified)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(first["password"]))
        with self.assertRaises(CommandError):
            _call("e2e_create_user", "--suffix", "run-001")

    # TST-APP-017
    def test_simulate_journey_respeita_term_explicito(self) -> None:
        term = json.loads(_call("e2e_create_term", "--year", "9101"))
        output = _call(
            "simulate_journey",
            "--modality",
            "project",
            "--submit",
            "--term",
            str(term["id"]),
            "--json",
        )
        application = ServiceApplication.objects.get(
            protocol=json.loads(output.strip().splitlines()[-1])["protocol"]
        )
        self.assertEqual(application.term_id, term["id"])

    # TST-APP-018
    def test_inspect_application_emite_taxas_eventos_e_nao_encontrado(self) -> None:
        term = AcademicTerm.objects.create(year=2098, period="first")
        owner = User.objects.create_user(username="inspect", email="inspect@example.com")
        application = ServiceApplication.objects.create(
            protocol="000000123",
            term=term,
            owner=owner,
            modality="consultation",
            researcher_name="Inspeção Teste",
            contact_email="inspecao@example.com",
            lifecycle_status="awaiting_payment",
        )
        FeeRequirement.objects.create(
            application=application,
            fee_type="application_fee",
            base_amount=Decimal("140.00"),
            amount=Decimal("140.00"),
            reason="Taxa de inscrição",
        )
        data = json.loads(_call("inspect_application", "--protocol", "000000123"))
        self.assertEqual(data["protocol"], "000000123")
        self.assertEqual(data["owner"], "inspect")
        self.assertEqual(data["fees"][0]["type"], "application_fee")
        with self.assertRaises(CommandError):
            call_command("inspect_application", "--protocol", "999999999")


class CleanupCommandTests(TestCase):
    # TST-APP-019
    def test_cleanup_remove_protocolo_termo_vazio_e_desativa_email(self) -> None:
        term = AcademicTerm.objects.create(year=2097, period="first")
        empty_term = AcademicTerm.objects.create(year=2096, period="first")
        owner = User.objects.create_user(
            username="cleanup", email="cleanup@example.com", is_active=True
        )
        application = ServiceApplication.objects.create(
            protocol="000000456",
            term=term,
            owner=owner,
            modality="consultation",
            researcher_name="Limpeza Teste",
            contact_email="cleanup@example.com",
            lifecycle_status="awaiting_payment",
        )
        _call(
            "e2e_cleanup",
            "--protocol",
            application.protocol,
            "--term-id",
            str(empty_term.pk),
            "--term-id",
            str(term.pk),
            "--deactivate-email",
            owner.email,
        )
        application.refresh_from_db()
        owner.refresh_from_db()
        self.assertIsNotNone(application.soft_deleted_at)
        self.assertFalse(AcademicTerm.objects.filter(pk=empty_term.pk).exists())
        self.assertTrue(AcademicTerm.objects.filter(pk=term.pk).exists())
        self.assertFalse(owner.is_active)

    # TST-APP-020
    def test_cleanup_sem_argumentos_nao_falha(self) -> None:
        output = _call("e2e_cleanup")
        self.assertIn("Nenhum item", output)

    # TST-APP-021
    def test_cleanup_purga_apenas_namespace_e2e(self) -> None:
        namespace_term = AcademicTerm.objects.create(year=9000, period="first")
        seed_term = AcademicTerm.objects.create(year=2036, period="first")
        owner = User.objects.create_user(
            username="purge", email="purge@example.com"
        )
        ServiceApplication.objects.create(
            protocol="000000555",
            term=namespace_term,
            owner=owner,
            modality="consultation",
            researcher_name="Purge Teste",
            contact_email="purge@example.com",
            lifecycle_status="awaiting_payment",
        )
        application = ServiceApplication.all_objects.get(protocol="000000555")
        FeeRequirement.objects.create(
            application=application,
            fee_type="application_fee",
            base_amount=Decimal("140.00"),
            amount=Decimal("140.00"),
            reason="Taxa de inscrição",
        )
        _call("e2e_cleanup", "--purge-e2e-terms")
        self.assertFalse(AcademicTerm.objects.filter(pk=namespace_term.pk).exists())
        self.assertFalse(
            ServiceApplication.all_objects.filter(protocol="000000555").exists()
        )
        self.assertTrue(AcademicTerm.objects.filter(pk=seed_term.pk).exists())


class MailboxCommandTests(TestCase):
    # TST-APP-022
    def test_mailbox_filtra_por_destinatario_assunto_e_ultima(self) -> None:
        directory = tempfile.mkdtemp(prefix="cea-mailbox-")
        with override_settings(
            DEBUG=True,
            EMAIL_BACKEND="django.core.mail.backends.filebased.EmailBackend",
            EMAIL_FILE_PATH=directory,
        ):
            mail.send_mail("Assunto A", "corpo A", "from@example.com", ["a@example.com"])
            mail.send_mail("Assunto B", "corpo B", "from@example.com", ["b@example.com"])
            filtered = json.loads(
                _call("e2e_mailbox", "--to", "b@example.com", "--json")
            )
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["subject"], "Assunto B")
            latest = json.loads(
                _call(
                    "e2e_mailbox",
                    "--subject-contains",
                    "Assunto",
                    "--latest",
                    "--json",
                )
            )
            self.assertEqual(len(latest), 1)
        self.assertTrue(Path(directory).is_dir())

    # TST-APP-023
    def test_mailbox_exige_backend_filebased_e_debug(self) -> None:
        with (
            override_settings(
                DEBUG=True,
                EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            ),
            self.assertRaises(CommandError),
        ):
            call_command("e2e_mailbox")
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("e2e_mailbox")


@override_settings(DEBUG=True)
class BackdateBankSlipCommandTests(TestCase):
    # TST-APP-024
    def test_recua_vencimento_do_boleto(self) -> None:
        term = AcademicTerm.objects.create(year=2095, period="first")
        owner = User.objects.create_user(username="slip", email="slip@example.com")
        application = ServiceApplication.objects.create(
            protocol="000000789",
            term=term,
            owner=owner,
            modality="consultation",
            researcher_name="Boleto Teste",
            contact_email="slip@example.com",
            lifecycle_status="awaiting_payment",
        )
        fee = FeeRequirement.objects.create(
            application=application,
            fee_type="application_fee",
            base_amount=Decimal("140.00"),
            amount=Decimal("140.00"),
            reason="Taxa de inscrição",
        )
        instrument = PaymentInstrument.objects.create(
            fee_requirement=fee,
            method="bank_slip",
            state="active",
            amount=Decimal("140.00"),
        )
        slip = BankSlipPaymentInstrument.objects.create(
            payment_instrument=instrument,
            bank_slip_reference="slip-e2e-1",
            due_date=timezone.localdate() + timedelta(days=3),
            document_amount=Decimal("140.00"),
        )
        _call("e2e_backdate_bank_slip", "--protocol", application.protocol)
        slip.refresh_from_db()
        self.assertEqual(slip.due_date, timezone.localdate() - timedelta(days=1))


@override_settings(DEBUG=True)
class ImportedApplicationFixtureTests(TestCase):
    # TST-APP-025
    def test_cria_inscricao_legada_sem_dono_e_e_idempotente(self) -> None:
        AcademicTerm.objects.create(year=2094, period="first")
        first = json.loads(
            _call(
                "e2e_create_imported_application",
                "--protocol",
                "000000321",
                "--contact-email",
                "legado@example.com",
            )
        )
        second = json.loads(
            _call(
                "e2e_create_imported_application",
                "--protocol",
                "000000321",
                "--contact-email",
                "legado@example.com",
            )
        )
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        application = ServiceApplication.all_objects.get(protocol="000000321")
        self.assertIsNone(application.owner)
        self.assertEqual(application.origin, ServiceApplication.Origin.IMPORTED)

    # TST-APP-026
    def test_comando_exige_debug(self) -> None:
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command(
                "e2e_create_imported_application",
                "--protocol",
                "000000654",
                "--contact-email",
                "x@example.com",
            )
