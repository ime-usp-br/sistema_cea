from typing import Any

from django.core.management.base import BaseCommand, CommandError

from ...importers import LegacyImporter
from ...sql_dump import build_records, read_dump


class Command(BaseCommand):
    help = (
        "Importa o dump SQL (MariaDB) do sistema legado, preservando inscrições, "
        "catálogo, pagamentos, triagens, reuniões, eventos e arquivos."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dump",
            type=str,
            required=True,
            help="Caminho do arquivo .sql gerado pelo mysqldump/mariadb-dump.",
        )
        parser.add_argument(
            "--storage-root",
            type=str,
            default="",
            help=(
                "Diretório raiz dos arquivos legados. Se omitido, anexos e "
                "comprovantes são ignorados."
            ),
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Atualiza inscrições importadas já existentes (reimportação).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limita a quantidade de inscrições processadas (para testes).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dump_path = options["dump"]
        try:
            dump = read_dump(dump_path)
        except FileNotFoundError as exc:
            raise CommandError(f"Dump não encontrado: {dump_path}") from exc
        records = build_records(dump)
        limit = options.get("limit") or 0
        if limit > 0:
            records = records[:limit]

        importer = LegacyImporter(
            attachments_root=options.get("storage_root") or None,
            update_existing=bool(options.get("update")),
        )
        report = importer.import_records(records)

        self.stdout.write(
            self.style.SUCCESS(f"Inscrições processadas: {report.created_count}")
        )
        for application in report.created:
            self.stdout.write(
                f"  - {application.protocol} ({application.get_modality_display()})"
            )
        for error in report.errors:
            self.stdout.write(self.style.ERROR(f"Erro: {error}"))
        for warning in report.warnings:
            self.stdout.write(self.style.WARNING(f"Aviso: {warning}"))
        for missing in report.missing_files:
            self.stdout.write(self.style.WARNING(f"Arquivo ausente: {missing}"))
        if report.errors:
            self.stdout.write(self.style.WARNING("Importação concluída com ressalvas."))
        else:
            self.stdout.write(self.style.SUCCESS("Importação concluída."))
