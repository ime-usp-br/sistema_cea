import os
import shutil
import tempfile
from datetime import date
from io import StringIO
from typing import Any

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from applications.models import (
    ApplicationAttachment,
    ApplicationEvent,
    ServiceApplication,
)
from files.models import FileAsset
from imports.sql_dump import (
    APPLICATION_COLUMNS,
    ATTACHMENT_COLUMNS,
    BANK_SLIP_COLUMNS,
    CONSULTATION_COLUMNS,
    DEPOSIT_RECEIPT_COLUMNS,
    EVENT_COLUMNS,
    SEMESTER_COLUMNS,
    TRIAGE_COLUMNS,
    build_records,
    read_dump,
)
from meetings.models import ConsultationMeeting, ProjectScreening
from payments.models import FeeRequirement, PaymentInstrument


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{text}'"


def _insert(table: str, columns: list[str], rows: list[dict[str, Any]]) -> str:
    values = []
    for row in rows:
        values.append(
            "(" + ", ".join(_sql_literal(row.get(column)) for column in columns) + ")"
        )
    return f"INSERT INTO `{table}` VALUES {', '.join(values)};\n"


def build_dump() -> str:
    return (
        _insert(
            "semesters",
            SEMESTER_COLUMNS,
            [
                {
                    "id": 1,
                    "year": 2025,
                    "period": "1° Semestre",
                    "started_at": "2025-03-01 00:00:00",
                    "finished_at": "2025-07-01 00:00:00",
                    "start_date_enrollments": "2025-02-01 00:00:00",
                    "end_date_enrollments": "2025-02-28 00:00:00",
                    "created_at": "2025-01-01 00:00:00",
                    "updated_at": "2025-01-01 00:00:00",
                },
                {
                    "id": 2,
                    "year": 2025,
                    "period": "2° Semestre",
                    "started_at": "2025-08-01 00:00:00",
                    "finished_at": "2025-12-01 00:00:00",
                    "start_date_enrollments": "2025-07-01 00:00:00",
                    "end_date_enrollments": "2025-07-31 00:00:00",
                    "created_at": "2025-01-01 00:00:00",
                    "updated_at": "2025-01-01 00:00:00",
                },
            ],
        )
        + _insert(
            "applications",
            APPLICATION_COLUMNS,
            [
                {
                    "id": 1,
                    "semesterID": 1,
                    "transfer_pending": 0,
                    "protocol": "123456789",
                    "projectResponsible": "Pesquisador Um",
                    "contactPhone": "11 99999-0000",
                    "CPFCNPJ": "111.111.111-11",
                    "email": "um@example.com",
                    "institution": "USP",
                    "institutionRelationship": "Doutorando",
                    "mentor": "Orientador",
                    "projectPurpose": "Doutorado,Publicação",
                    "fundingAgency": "FAPESP,Outra",
                    "faOther": "CAPES",
                    "knowledgeArea": "Médica ou Biológica,Outra",
                    "kaOther": "Saúde",
                    "bdName": "Fulano",
                    "bdCpfCnpj": "111.111.111-11",
                    "bdBankName": "Banco X",
                    "bdAgency": "1234",
                    "bdAccount": "5678-9",
                    "bdType": "Corrente",
                    "projectTitle": "Projeto X",
                    "generalAspects": "Aspectos",
                    "generalObjectives": "Objetivos",
                    "features": "Variáveis",
                    "otherFeatures": "Outras",
                    "limitations": "Limitações",
                    "storage": "Armazenamento",
                    "conclusions": "Conclusões",
                    "expectedHelp": "Ajuda",
                    "created_at": "2025-03-01 10:00:00",
                    "updated_at": "2025-03-02 11:00:00",
                    "serviceType": "Projeto",
                    "refundReceipt": "Sim",
                    "refundReceiptData": "Recibo",
                    "status": "Aprovado como projeto",
                    "course": "Curso",
                    "dataCollect": "Sim",
                    "deleted": 0,
                    "whatsapp": 1,
                },
                {
                    "id": 2,
                    "semesterID": 2,
                    "transfer_pending": 1,
                    "protocol": "987654321",
                    "projectResponsible": "Pesquisador Dois",
                    "email": "dois@example.com",
                    "institution": "USP",
                    "institutionRelationship": "Professor",
                    "projectPurpose": "Mestrado",
                    "knowledgeArea": "Tecnológica",
                    "projectTitle": "Consulta Y",
                    "generalAspects": "Aspectos 2",
                    "generalObjectives": "Objetivos 2",
                    "features": "Variáveis 2",
                    "otherFeatures": "Outras 2",
                    "limitations": "Limitações 2",
                    "storage": "Armazenamento 2",
                    "conclusions": "Conclusões 2",
                    "expectedHelp": "Ajuda 2",
                    "created_at": "2025-08-01 10:00:00",
                    "updated_at": "2025-08-02 11:00:00",
                    "serviceType": "Consulta",
                    "refundReceipt": "Não",
                    "status": "Aguardando resultado da reunião de consulta",
                    "course": "Curso 2",
                    "dataCollect": "Não",
                    "deleted": 1,
                    "whatsapp": 0,
                },
            ],
        )
        + _insert(
            "bank_slips",
            BANK_SLIP_COLUMNS,
            [
                {
                    "id": 1,
                    "applicationID": 1,
                    "relativoA": "Taxa de Inscrição (Substituído)",
                    "codigoIDBoleto": "COD1",
                    "dataVencimentoBoleto": "20/03/2025",
                    "valorDocumento": 80.0,
                    "valorDesconto": 0.0,
                    "valorEfetivamentePago": 0.0,
                    "statusBoletoBancario": "C",
                    "manual_payment_confirmed": 0,
                    "created_at": "2025-03-01 10:00:00",
                    "updated_at": "2025-03-01 10:00:00",
                },
                {
                    "id": 2,
                    "applicationID": 1,
                    "relativoA": "Taxa de Inscrição",
                    "codigoIDBoleto": "COD2",
                    "dataVencimentoBoleto": "25/03/2025",
                    "dataEfetivaPagamento": "24/03/2025",
                    "valorDocumento": 80.0,
                    "valorDesconto": 0.0,
                    "valorEfetivamentePago": 80.0,
                    "statusBoletoBancario": "P",
                    "manual_payment_confirmed": 1,
                    "manual_payment_confirmed_at": "2025-03-24 12:00:00",
                    "manual_payment_confirmed_by": "Secretaria",
                    "created_at": "2025-03-01 10:00:00",
                    "updated_at": "2025-03-01 10:00:00",
                },
                {
                    "id": 3,
                    "applicationID": 1,
                    "relativoA": "Taxa de Projeto",
                    "codigoIDBoleto": "COD3",
                    "dataVencimentoBoleto": "30/03/2025",
                    "dataEfetivaPagamento": "29/03/2025",
                    "valorDocumento": 200.0,
                    "valorDesconto": 0.0,
                    "valorEfetivamentePago": 200.0,
                    "statusBoletoBancario": "P",
                    "manual_payment_confirmed": 0,
                    "created_at": "2025-03-01 10:00:00",
                    "updated_at": "2025-03-01 10:00:00",
                },
                {
                    "id": 4,
                    "applicationID": 2,
                    "relativoA": "Taxa de Inscrição",
                    "codigoIDBoleto": "COD4",
                    "dataVencimentoBoleto": "10/08/2025",
                    "valorDocumento": 140.0,
                    "valorDesconto": 0.0,
                    "valorEfetivamentePago": 0.0,
                    "statusBoletoBancario": "E",
                    "manual_payment_confirmed": 0,
                    "created_at": "2025-08-01 10:00:00",
                    "updated_at": "2025-08-01 10:00:00",
                },
            ],
        )
        + _insert(
            "attachments",
            ATTACHMENT_COLUMNS,
            [
                {
                    "id": "a1",
                    "name": "arquivo.pdf",
                    "path": "123456789/arquivo.pdf",
                    "applicationID": 1,
                    "created_at": "2025-03-01 12:00:00",
                    "updated_at": "2025-03-01 12:00:00",
                }
            ],
        )
        + _insert(
            "deposit_receipts",
            DEPOSIT_RECEIPT_COLUMNS,
            [
                {
                    "id": "d1",
                    "name": "comprovante.pdf",
                    "path": "123456789/comprovante.pdf",
                    "applicationID": 1,
                    "created_at": "2025-03-01 13:00:00",
                    "updated_at": "2025-03-01 13:00:00",
                }
            ],
        )
        + _insert(
            "triages",
            TRIAGE_COLUMNS,
            [
                {
                    "id": 1,
                    "applicationID": 1,
                    "date": "15/08",
                    "hour": "10:00",
                    "meetingMode": "Online",
                    "link": "https://meet.example",
                    "decision": "Aprovado como projeto",
                    "note": "ok",
                    "created_at": "2025-05-01 10:00:00",
                    "updated_at": "2025-05-01 11:00:00",
                    "feedback": "Triagem Realizada",
                }
            ],
        )
        + _insert(
            "consultation_meetings",
            CONSULTATION_COLUMNS,
            [
                {
                    "id": 1,
                    "applicationID": 2,
                    "date": "20/09/2025",
                    "hour": "14:30",
                    "meetingMode": "Presencial",
                    "local": "Sala 1",
                    "decision": "Aprovado como Consulta",
                    "note": "ok",
                    "created_at": "2025-09-01 10:00:00",
                    "updated_at": "2025-09-01 11:00:00",
                    "feedback": "Consulta realizada",
                }
            ],
        )
        + _insert(
            "events",
            EVENT_COLUMNS,
            [
                {
                    "id": 1,
                    "applicationID": 1,
                    "name": "Taxa de inscrição",
                    "description": "pagamento",
                    "event_date": "2025-03-01 10:00:00",
                    "created_at": "2025-03-01 10:00:00",
                    "updated_at": "2025-03-01 10:00:00",
                },
                {
                    "id": 2,
                    "applicationID": 2,
                    "name": "Inscrição",
                    "event_date": "2025-08-01 09:00:00",
                    "created_at": "2025-08-01 09:00:00",
                    "updated_at": "2025-08-01 09:00:00",
                },
            ],
        )
    )


class SqlDumpTests(TestCase):
    def setUp(self) -> None:
        self.media_root = tempfile.mkdtemp(prefix="cea-sql-dump-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".sql", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(build_dump())
            self.dump_path = handle.name

    def tearDown(self) -> None:
        self.override.disable()
        os.unlink(self.dump_path)
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_read_dump_extrai_tabelas(self) -> None:
        dump = read_dump(self.dump_path)
        self.assertEqual(len(dump["applications"]), 2)
        self.assertEqual(len(dump["semesters"]), 2)
        self.assertEqual(len(dump["bank_slips"]), 4)
        self.assertEqual(len(dump["attachments"]), 1)
        self.assertEqual(len(dump["deposit_receipts"]), 1)
        self.assertEqual(len(dump["triages"]), 1)
        self.assertEqual(len(dump["consultation_meetings"]), 1)
        self.assertEqual(len(dump["events"]), 2)

    def test_build_records_mapeia_inscricao_completa(self) -> None:
        records = build_records(read_dump(self.dump_path))
        record = records[0]

        self.assertEqual(record["protocol"], "123456789")
        self.assertEqual(record["modality"], "project")
        self.assertEqual(record["context_summary"], "Aspectos")
        self.assertEqual(record["general_objectives"], "Objetivos")
        self.assertEqual(record["variables_and_measurements"], "Variáveis")
        self.assertEqual(record["contextual_factors"], "Outras")
        self.assertEqual(record["sampling_and_limitations"], "Limitações")
        self.assertEqual(record["data_management_plan"], "Armazenamento")
        self.assertEqual(record["expected_results"], "Conclusões")
        self.assertEqual(record["expected_support"], "Ajuda")
        self.assertTrue(record["data_already_collected"])
        self.assertTrue(record["wants_refund_receipt"])
        self.assertEqual(record["refund_bank_account_type"], "checking")
        self.assertTrue(record["has_whatsapp"])
        self.assertEqual(record["term"]["year"], 2025)
        self.assertEqual(record["term"]["period"], "first")
        self.assertEqual(record["term"]["teaching_start_date"], date(2025, 3, 1))

        codes = {(item["category"], item["code"]) for item in record["catalog_options"]}
        self.assertIn(("project_purpose", "doctorate"), codes)
        self.assertIn(("project_purpose", "publication"), codes)
        self.assertIn(("knowledge_area", "health_biological"), codes)
        self.assertIn(("knowledge_area", "other"), codes)
        self.assertIn(("funding_agency", "fapesp"), codes)
        self.assertIn(("funding_agency", "other"), codes)
        self.assertIn(("institutional_tie", "student"), codes)

        self.assertEqual(len(record["payments"]), 3)
        self.assertEqual(record["payments"][0]["bank_slip"]["reference"], "COD1")
        self.assertEqual(record["payments"][0]["state"], "canceled")

        self.assertEqual(len(record["triages"]), 1)
        self.assertEqual(record["triages"][0]["scheduled_date"], date(2025, 8, 15))
        self.assertEqual(record["triages"][0]["decision"], "approved_as_project")
        self.assertEqual(
            record["triages"][0]["teacher_feedback"], "screening_completed"
        )
        self.assertEqual(record["events"][0]["event_code"], "legacy.Taxa de inscrição")
        self.assertEqual(record["attachments"][0]["original_filename"], "arquivo.pdf")
        self.assertEqual(
            record["deposit_receipts"][0]["original_filename"], "comprovante.pdf"
        )

        consultation = records[1]
        self.assertEqual(consultation["modality"], "consultation")
        self.assertIsNotNone(consultation["soft_deleted_at"])
        self.assertTrue(consultation["transfer_pending"])
        self.assertEqual(
            consultation["consultation_meetings"][0]["decision"],
            "approved_as_consultation",
        )
        self.assertEqual(
            consultation["consultation_meetings"][0]["teacher_feedback"],
            "consultation_completed",
        )

    def test_command_importa_com_storage_e_reimporta_sem_duplicar(self) -> None:
        storage_root = os.path.join(self.media_root, "legacy")
        os.makedirs(os.path.join(storage_root, "123456789"))
        with open(os.path.join(storage_root, "123456789", "arquivo.pdf"), "wb") as handle:
            handle.write(b"%PDF-1.4")
        with open(
            os.path.join(storage_root, "123456789", "comprovante.pdf"), "wb"
        ) as handle:
            handle.write(b"imagem")

        call_command(
            "import_legacy_sql",
            dump=self.dump_path,
            storage_root=storage_root,
            stdout=StringIO(),
        )

        self.assertEqual(
            ServiceApplication.all_objects.filter(origin="imported").count(), 2
        )
        app = ServiceApplication.all_objects.get(protocol="123456789")
        self.assertEqual(app.fee_requirements.count(), 2)
        self.assertEqual(
            app.fee_requirements.get(fee_type="application_fee")
            .payment_instruments.count(),
            2,
        )
        self.assertEqual(app.catalog_selections.count(), 7)
        self.assertTrue(ProjectScreening.objects.filter(application=app).exists())
        self.assertTrue(ApplicationAttachment.objects.filter(application=app).exists())
        self.assertEqual(
            FileAsset.objects.filter(
                application=app, purpose=FileAsset.Purpose.PAYMENT_RECEIPT
            ).count(),
            1,
        )
        self.assertTrue(
            ApplicationEvent.objects.filter(
                application=app, event_code__startswith="legacy."
            ).exists()
        )
        self.assertEqual(
            PaymentInstrument.objects.filter(
                fee_requirement__application=app,
                state=PaymentInstrument.State.PAID,
            ).count(),
            2,
        )

        consultation = ServiceApplication.all_objects.get(protocol="987654321")
        self.assertIsNotNone(consultation.soft_deleted_at)
        self.assertTrue(
            ConsultationMeeting.objects.filter(application=consultation).exists()
        )

        call_command(
            "import_legacy_sql",
            dump=self.dump_path,
            storage_root=storage_root,
            update=True,
            stdout=StringIO(),
        )

        self.assertEqual(
            ServiceApplication.all_objects.filter(origin="imported").count(), 2
        )
        self.assertEqual(FeeRequirement.objects.count(), 3)
        self.assertEqual(
            ApplicationAttachment.objects.filter(application=app).count(), 1
        )
        self.assertEqual(
            FileAsset.objects.filter(
                application=app, purpose=FileAsset.Purpose.PAYMENT_RECEIPT
            ).count(),
            1,
        )

    def test_command_sem_storage_ignora_arquivos_e_avisa(self) -> None:
        output = StringIO()
        call_command(
            "import_legacy_sql",
            dump=self.dump_path,
            stdout=output,
        )
        app = ServiceApplication.all_objects.get(protocol="123456789")
        self.assertFalse(ApplicationAttachment.objects.filter(application=app).exists())
        self.assertEqual(FileAsset.objects.filter(application=app).count(), 0)
        self.assertIn("storage", output.getvalue().lower())

    def test_command_limit_processa_apenas_um(self) -> None:
        call_command(
            "import_legacy_sql",
            dump=self.dump_path,
            limit=1,
            stdout=StringIO(),
        )
        self.assertEqual(
            ServiceApplication.all_objects.filter(origin="imported").count(), 1
        )

    def test_command_dump_inexistente_gera_erro(self) -> None:
        with self.assertRaises(CommandError):
            call_command(
                "import_legacy_sql",
                dump="/tmp/dump-que-nao-existe.sql",
                stdout=StringIO(),
            )
