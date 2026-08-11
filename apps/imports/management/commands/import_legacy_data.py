from typing import Any

from django.core.management.base import BaseCommand

from ...importers import LegacyImporter

EXAMPLE_RECORDS: list[dict[str, Any]] = [
    {
        "protocol": "100000001",
        "modality": "project",
        "researcher_name": "Ana Importada",
        "contact_email": "ana@example.com",
        "tax_id": "11111111111",
        "legacy_contact_email": "ana@example.com",
        "legacy_contact_tax_id": "11111111111",
        "project_title": "Projeto legado A",
        "lifecycle_status": "submitted",
        "term": {"year": 2025, "period": "first"},
        "payments": [
            {
                "method": "bank_slip",
                "state": "paid",
                "amount": "80.00",
                "reason": "Taxa de inscrição importada",
            }
        ],
    },
    {
        "protocol": "100000002",
        "modality": "consultation",
        "researcher_name": "Bruno Importado",
        "contact_email": "bruno@example.com",
        "tax_id": "22222222222",
        "legacy_contact_email": "bruno@example.com",
        "legacy_contact_tax_id": "22222222222",
        "lifecycle_status": "submitted",
        "term": {"year": 2025, "period": "first"},
    },
]


class Command(BaseCommand):
    help = "Importa inscrições de tabelas legadas, preservando contatos e pagamentos."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--data",
            type=str,
            default="",
            help="Caminho de arquivo JSON com a lista de registros. Se omitido, usa dados de exemplo.",
        )
        parser.add_argument(
            "--attachments-root",
            type=str,
            default="",
            help="Diretório raiz onde ficam os arquivos legados referenciados em attachments.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        importer = LegacyImporter(
            attachments_root=options.get("attachments_root") or None
        )
        data_path = options.get("data") or ""
        records = (
            importer.load_records_from_file(data_path)
            if data_path
            else EXAMPLE_RECORDS
        )
        report = importer.import_records(records)
        self.stdout.write(self.style.SUCCESS(f"Criadas: {report.created_count}"))
        for protocol in report.created:
            self.stdout.write(f"  - {protocol.protocol} ({protocol.get_modality_display()})")
        for error in report.errors:
            self.stdout.write(self.style.ERROR(f"Erro: {error}"))
        for missing in report.missing_files:
            self.stdout.write(self.style.WARNING(f"Arquivo ausente: {missing}"))
        if report.errors:
            self.stdout.write(self.style.WARNING("Importação concluída com ressalvas."))
