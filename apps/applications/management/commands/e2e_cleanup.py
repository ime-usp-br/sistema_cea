"""Cleanup dos dados criados pela suíte E2E (T3.1).

Os protocolos criados são marcados com exclusão lógica (``soft_deleted_at``),
preservando a retenção exigida. Períodos criados pela suíte só são removidos se
estiverem vazios e usuários de teste são desativados, sem apagar histórico.

Com ``--purge-e2e-terms``, o comando remove fisicamente apenas os dados do
namespace E2E (anos 9000–9999), inclusive inscrições já soft-deleted. Essa
opção existe exclusivamente para a stack descartável de testes e não deve ser
usada em ambientes com dados reais.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Marca como excluídas (soft delete) as inscrições E2E informadas por protocolo."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--protocol",
            action="append",
            default=[],
            dest="protocols",
            help="Protocolo de uma inscrição criada pelo E2E (pode repetir).",
        )
        parser.add_argument(
            "--term-id",
            action="append",
            type=int,
            default=[],
            dest="term_ids",
            help="Período letivo criado pelo E2E (removido se não tiver inscrições).",
        )
        parser.add_argument(
            "--deactivate-email",
            action="append",
            default=[],
            dest="emails",
            help="E-mail de usuário criado pelo E2E (desativado ao final).",
        )
        parser.add_argument(
            "--deactivate-prefix",
            action="append",
            default=[],
            dest="email_prefixes",
            help="Desativa usuários cujo e-mail começa com o prefixo (pode repetir).",
        )
        parser.add_argument(
            "--deactivate-codpes",
            action="append",
            default=[],
            dest="codpes_values",
            help="Desativa usuários criados pelo E2E pelo número USP (pode repetir).",
        )
        parser.add_argument(
            "--purge-e2e-terms",
            action="store_true",
            help=(
                "Remove fisicamente inscrições e períodos do namespace E2E "
                "(anos 9000–9999). Uso exclusivo da stack descartável de testes."
            ),
        )
        parser.add_argument(
            "--purge-protocol",
            action="append",
            default=[],
            dest="purge_protocols",
            help="Remove fisicamente apenas a inscrição do protocolo indicado.",
        )
        parser.add_argument("--namespace-start", type=int, default=9000)
        parser.add_argument("--namespace-end", type=int, default=9999)

    def handle(self, *args: Any, **options: Any) -> None:
        from applications.models import ServiceApplication
        from terms.models import AcademicTerm
        from users.models import User

        protocols: list[str] = options["protocols"]
        if protocols:
            queryset = ServiceApplication.all_objects.filter(
                protocol__in=protocols, soft_deleted_at__isnull=True
            )
            updated = queryset.update(
                soft_deleted_at=timezone.now(), updated_at=timezone.now()
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{updated} inscrição(ões) E2E marcada(s) como excluída(s)."
                )
            )

        for term_id in options["term_ids"]:
            term = AcademicTerm.objects.filter(pk=term_id).first()
            if term is None:
                continue
            # Só remove períodos criados pela suíte e sem qualquer inscrição
            # (inclusive soft-deleted), preservando o seed e os dados de DEV.
            if ServiceApplication.all_objects.filter(term=term).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Período {term_id} possui inscrições; mantido."
                    )
                )
                continue
            term.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Período E2E {term_id} removido.")
            )

        emails: list[str] = options["emails"]
        if emails:
            updated_users = User.objects.filter(
                email__in=emails, is_active=True
            ).update(is_active=False, updated_at=timezone.now())
            self.stdout.write(
                self.style.SUCCESS(
                    f"{updated_users} usuário(s) E2E desativado(s)."
                )
            )

        seed_usernames = {
            "e2e_candidate",
            "e2e_teacher",
            "e2e_secretariat",
            "e2e_admin",
        }
        for prefix in options["email_prefixes"]:
            updated_users = (
                User.objects.filter(
                    email__istartswith=prefix, is_active=True
                )
                .exclude(username__in=seed_usernames)
                .update(is_active=False, updated_at=timezone.now())
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{updated_users} usuário(s) com prefixo {prefix!r} desativado(s)."
                )
            )

        for codpes in options["codpes_values"]:
            try:
                codpes_value = int(codpes)
            except (TypeError, ValueError):
                continue
            updated_users = (
                User.objects.filter(codpes=codpes_value, is_active=True)
                .exclude(username__in=seed_usernames)
                .update(is_active=False, updated_at=timezone.now())
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{updated_users} usuário(s) com codpes {codpes_value} desativado(s)."
                )
            )

        purge_protocols: list[str] = options["purge_protocols"]
        if purge_protocols or options["purge_e2e_terms"]:
            from django.db import transaction

            from audits.models import DatasetAuditResolution, DatasetAuditSubmission
            from meetings.models import ConsultationMeeting, ProjectScreening
            from payments.models import FeeRequirement, PaymentInstrument, RefundRequest

            with transaction.atomic():
                if purge_protocols:
                    applications = ServiceApplication.all_objects.filter(
                        protocol__in=purge_protocols
                    )
                else:
                    applications = ServiceApplication.all_objects.filter(
                        term__year__gte=options["namespace_start"],
                        term__year__lte=options["namespace_end"],
                    )
                application_ids = list(applications.values_list("pk", flat=True))
                applications_count = len(application_ids)
                # FKs com on_delete=RESTRICT precisam sair antes da inscrição.
                DatasetAuditResolution.objects.filter(
                    application_id__in=application_ids
                ).delete()
                DatasetAuditSubmission.objects.filter(
                    application_id__in=application_ids
                ).delete()
                RefundRequest.objects.filter(application_id__in=application_ids).delete()
                ProjectScreening.objects.filter(
                    application_id__in=application_ids
                ).delete()
                ConsultationMeeting.objects.filter(
                    application_id__in=application_ids
                ).delete()
                PaymentInstrument.objects.filter(
                    fee_requirement__application_id__in=application_ids
                ).delete()
                FeeRequirement.objects.filter(application_id__in=application_ids).delete()
                applications.delete()
                terms_count = 0
                if not purge_protocols:
                    terms = AcademicTerm.objects.filter(
                        year__gte=options["namespace_start"],
                        year__lte=options["namespace_end"],
                    )
                    terms_count = terms.count()
                    terms.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Namespace E2E limpo: {applications_count} inscrição(ões) e "
                    f"{terms_count} período(s) removidos."
                )
            )

        if (
            not protocols
            and not options["term_ids"]
            and not emails
            and not options["email_prefixes"]
            and not options["codpes_values"]
            and not options["purge_protocols"]
            and not options["purge_e2e_terms"]
        ):
            self.stdout.write(
                self.style.WARNING("Nenhum item informado; nada a limpar.")
            )
